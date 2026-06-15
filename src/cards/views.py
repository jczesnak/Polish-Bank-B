from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status, generics
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal, InvalidOperation

from accounts.models import Account
from .models import PaymentCard, CardTransaction
from .serializers import CardTransactionSerializer
from .services import CardIntegrationService

class OrderCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account = get_object_or_404(Account, user=request.user)
        
        card_type = request.data.get("card_type", "VIRTUAL")
        initial_balance = request.data.get("initial_balance", 0.0)
        
        card_service = CardIntegrationService()
        result = card_service.order_card(account=account, card_type=card_type, initial_balance=initial_balance)
        
        if result.get("success"):
            return Response({
                "message": "Karta została wygenerowana pomyślnie.",
                "masked_number": result["masked_number"],
                "expiry_date": result["expiry_date"],
                "cvv": result["cvv"],
                "card_type": card_type
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "error": "Odrzucenie z systemu procesora kart.",
                "details": result.get("details"),
                "http_code": result.get("error_code")
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class UserCardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = get_object_or_404(Account, user=request.user)
        cards = account.cards.all()
        card_service = CardIntegrationService()
        
        result_cards = []
        for card in cards:
            data = {
                'id': card.id,
                'masked_number': card.masked_number,
                'is_active': card.is_active,
                'created_at': card.created_at
            }
            # Doczytywanie statusu zewnętrznego (np. PRODUCING, SHIPPED)
            details = card_service.get_card_details(card_token=card.external_card_id)
            if details.get("success"):
                data["status"] = details.get("status")
                data["card_type"] = details.get("card_type")
            result_cards.append(data)
            
        return Response(result_cards, status=status.HTTP_200_OK)

class AuthorizeWebhookView(APIView):
    permission_classes = [] # Webhook wywoływany przez procesor kart
    
    def post(self, request):
        # Dokumentacja procesora wymaga: {"account_id": "uuid", "amount": 150.00, ...}
        # Czasami procesor może wysłać card_token zamiast account_id, obsłużmy oba przypadki
        account_id = request.data.get("account_id")
        card_token = request.data.get("card_token")
        amount = request.data.get("amount")
        
        if not amount:
            return Response({"error": "Brak kwoty do autoryzacji"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            amount = Decimal(str(amount))
            
            with transaction.atomic():
                if account_id:
                    account = Account.objects.select_for_update().get(id=account_id)
                elif card_token:
                    card = PaymentCard.objects.select_related('account').get(external_card_id=card_token)
                    account = Account.objects.select_for_update().get(id=card.account.id)
                else:
                    return Response({"error": "Brak identyfikatora rachunku ani karty"}, status=status.HTTP_400_BAD_REQUEST)
                
                if account.available_balance >= amount:
                    account.blocked_funds += amount
                    account.save()
                    
                    if card_token:
                        CardTransaction.objects.create(
                            card=card,
                            amount=amount,
                            currency=request.data.get("currency", "PLN"),
                            merchant_name=request.data.get("merchant_id", "Nieznany sklep"),
                            status=CardTransaction.Status.AUTHORIZED
                        )
                        
                    return Response({
                        "authorization_code": f"AUTH-{str(account.id)[:6]}",
                        "status": "APPROVED",
                        "decline_reason": None
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        "authorization_code": None,
                        "status": "DECLINED",
                        "decline_reason": "INSUFFICIENT_FUNDS"
                    }, status=status.HTTP_200_OK)
                    
        except (Account.DoesNotExist, PaymentCard.DoesNotExist):
            return Response({
                "authorization_code": None,
                "status": "DECLINED",
                "decline_reason": "ACCOUNT_NOT_FOUND"
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class CaptureWebhookView(APIView):
    permission_classes = [] 

    def post(self, request):
        # Dokumentacja procesora mówi, że wywołuje ten endpoint z:
        # { "authorization_code": "AUTH-789XYZ", "transaction_id": "uuid", "amount": 150.00, "card_token": "..." }
        card_token = request.data.get("card_token")
        amount = request.data.get("amount")
        merchant_id = request.data.get("merchant_id", "Nieznany sklep")
        currency = request.data.get("currency", "PLN")
        
        if not card_token or amount is None:
            return Response({"error": "Brak parametrów do rozliczenia (card_token, amount)"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            amount = Decimal(str(amount))
            with transaction.atomic():
                card = PaymentCard.objects.select_related('account').get(external_card_id=card_token)
                account = Account.objects.select_for_update().get(id=card.account.id)
                
                # Zdejmujemy blokadę autoryzacyjną (zakładając, że cała kwota była zablokowana)
                if account.blocked_funds >= amount:
                    account.blocked_funds -= amount
                else:
                    account.blocked_funds = Decimal('0.00')
                    
                # Rzeczywiste obciążenie rachunku
                account.balance -= amount
                account.save()
                
                CardTransaction.objects.create(
                    card=card,
                    amount=amount,
                    currency=currency,
                    merchant_name=merchant_id,
                    status=CardTransaction.Status.SETTLED
                )
                
            return Response({"status": "SETTLED"}, status=status.HTTP_200_OK)
            
        except PaymentCard.DoesNotExist:
            return Response({"error": "Karta nie znaleziona"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class RefundWebhookView(APIView):
    permission_classes = []

    def post(self, request):
        card_token = request.data.get("card_token")
        amount = request.data.get("amount")
        merchant_id = request.data.get("merchant_id", "Nieznany sklep")
        currency = request.data.get("currency", "PLN")
        
        if not card_token or amount is None:
            return Response({"error": "Brak parametrów (card_token, amount)"}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            amount = Decimal(str(amount))
            with transaction.atomic():
                card = PaymentCard.objects.select_related('account').get(external_card_id=card_token)
                account = Account.objects.select_for_update().get(id=card.account.id)
                
                account.balance += amount
                account.save()
                
                CardTransaction.objects.create(
                    card=card,
                    amount=amount,
                    currency=currency,
                    merchant_name=merchant_id,
                    status=CardTransaction.Status.REFUNDED
                )
                
            return Response({"status": "REFUNDED"}, status=status.HTTP_200_OK)
        except PaymentCard.DoesNotExist:
            return Response({"error": "Karta nie znaleziona"}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class BlockCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)

        if not card.is_active:
            return Response({"error": "Karta jest już nieaktywna."}, status=status.HTTP_400_BAD_REQUEST)

        card_service = CardIntegrationService()
        result = card_service.block_card(card_token=card.external_card_id)

        if result.get("success"):
            card.is_active = False
            card.save()
            return Response({"message": "Karta została zablokowana (zawieszona)."}, status=status.HTTP_200_OK)
        else:
            return Response({
                "error": "Odrzucenie żądania blokady przez system procesora kart.",
                "details": result.get("details"),
                "http_code": result.get("error_code")
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class UnblockCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)

        if card.is_active:
            return Response({"error": "Karta jest już aktywna."}, status=status.HTTP_400_BAD_REQUEST)

        card_service = CardIntegrationService()
        result = card_service.unblock_card(card_token=card.external_card_id)

        if result.get("success"):
            card.is_active = True
            card.save()
            return Response({"message": "Karta została odblokowana."}, status=status.HTTP_200_OK)
        else:
            return Response({
                "error": "Odrzucenie żądania odblokowania przez system procesora kart.",
                "details": result.get("details"),
                "http_code": result.get("error_code")
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class DeleteCardView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)

        card_service = CardIntegrationService()
        if card.is_active:
            # Block it first at provider
            card_service.block_card(card_token=card.external_card_id, reason="Trwałe usunięcie (Bank)")

        # Usuwamy wpis w banku
        card.delete()
        return Response({"message": "Karta została trwale odpięta od rachunku."}, status=status.HTTP_200_OK)

class CardDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)
        
        card_service = CardIntegrationService()
        result = card_service.get_card_details(card_token=card.external_card_id)
        
        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)
        return Response({"error": "Nie można pobrać danych karty"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class ActivateCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)
        card_service = CardIntegrationService()
        result = card_service.activate_card(card_token=card.external_card_id)
        if result.get("success"):
            return Response({"message": "Karta została pomyślnie aktywowana."}, status=status.HTTP_200_OK)
        return Response({"error": result.get("details", "Błąd aktywacji karty.")}, status=status.HTTP_400_BAD_REQUEST)

class TopUpCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)
        amount = request.data.get("amount")
        try:
            amount = Decimal(str(amount))
            if amount <= Decimal("0.0"):
                raise ValueError
        except (TypeError, ValueError, InvalidOperation):
            return Response({"error": "Nieprawidłowa kwota doładowania."}, status=status.HTTP_400_BAD_REQUEST)

        # Pobieramy środki z konta użytkownika
        account = card.account
        if account.balance < amount:
            return Response({"error": "Brak wystarczających środków na koncie do doładowania karty."}, status=status.HTTP_400_BAD_REQUEST)

        card_service = CardIntegrationService()
        result = card_service.topup_prepaid(card_token=card.external_card_id, amount=amount)
        if result.get("success"):
            # Odejmujemy z konta
            account.balance -= amount
            account.save()
            return Response({"message": "Karta została pomyślnie doładowana.", "new_balance": result.get("new_balance")}, status=status.HTTP_200_OK)
        
        return Response({"error": result.get("details", "Błąd doładowania karty.")}, status=status.HTTP_400_BAD_REQUEST)

class DevSimulateShippingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)
        card_service = CardIntegrationService()
        result = card_service.dev_simulate_shipping(card_token=card.external_card_id)
        if result.get("success"):
            return Response({"message": "Symulacja udana. Karta wysłana (SHIPPED)."}, status=status.HTTP_200_OK)
        return Response({"error": result.get("details", "Błąd symulacji.")}, status=status.HTTP_400_BAD_REQUEST)

class CardTransactionListView(generics.ListAPIView):
    serializer_class = CardTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CardTransaction.objects.filter(card__account__user=self.request.user)