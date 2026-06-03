from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal

from accounts.models import Account
from .models import PaymentCard  
from .services import CardIntegrationService

class OrderCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        account = get_object_or_404(Account, user=request.user)
        
        card_service = CardIntegrationService()
        result = card_service.order_card(account=account)
        
        if result.get("success"):
            return Response({
                "message": "Karta została wygenerowana pomyślnie.",
                "masked_number": result["masked_number"],
                "expiry_date": result["expiry_date"],
                "cvv": result["cvv"]
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({
                "error": "Odrzucenie z systemu procesora kart.",
                "details": result.get("details"),
                "grpc_code": result.get("error_code")
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

class UserCardsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        account = get_object_or_404(Account, user=request.user)
        cards = account.cards.filter(is_active=True).values(
            'id', 'masked_number', 'created_at'
        )
        return Response(list(cards), status=status.HTTP_200_OK)
    
class CardSettlementWebhookView(APIView):
    permission_classes = [] # Publiczny endpoint dla webhooka

    def post(self, request):
        card_token = request.data.get("card_token")
        amount = request.data.get("amount")
        
        if not card_token or amount is None:
            return Response({"error": "Brak wymaganych parametrów (card_token, amount)."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            amount = Decimal(str(amount))
            
            with transaction.atomic():
                # select_for_update() blokuje wiersz, aby uniknąć błędów przy jednoczesnych płatnościach
                card = PaymentCard.objects.select_related('account').select_for_update().get(external_card_id=card_token)
                account = card.account
                
                account.balance -= amount
                account.save()
                
            return Response({"status": "settled", "new_balance": account.balance}, status=status.HTTP_200_OK)
            
        except PaymentCard.DoesNotExist:
            return Response({"error": "Karta nie istnieje w rejestrze banku."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"error": "Błąd przetwarzania rozliczenia.", "details": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class BlockCardView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        # Pobieramy kartę z bazy, upewniając się, że należy do rachunku zalogowanego usera.
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)

        if not card.is_active:
            return Response({"error": "Karta jest już nieaktywna."}, status=status.HTTP_400_BAD_REQUEST)

        # Inicjalizacja i wywołanie klienta gRPC
        card_service = CardIntegrationService()
        result = card_service.block_card(card_token=card.external_card_id)

        if result.get("success"):
            # Zmiana stanu w lokalnej bazie Django po udanej propagacji
            card.is_active = False
            card.save()
            return Response({"message": "Karta została zablokowana i odpięta od rachunku."}, status=status.HTTP_200_OK)
        else:
            return Response({
                "error": "Odrzucenie żądania blokady przez system procesora kart.",
                "details": result.get("details"),
                "grpc_code": result.get("error_code")
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        

class CardDetailsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, card_id):
        card = get_object_or_404(PaymentCard, id=card_id, account__user=request.user)
        
        card_service = CardIntegrationService()
        result = card_service.get_card_details(card_token=card.external_card_id)
        
        if result.get("success"):
            return Response(result, status=status.HTTP_200_OK)
        return Response({"error": "Nie można pobrać danych karty"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)