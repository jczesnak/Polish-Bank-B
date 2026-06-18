from decimal import Decimal

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Account, JuniorProfile, JuniorTransferRequest
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    AccountSerializer, UpdateProfileSerializer,
    JuniorCreateSerializer, JuniorProfileSerializer,
    JuniorTransferRequestSerializer,
)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        tokens = RefreshToken.for_user(user)
        return Response({
            'access': str(tokens.access_token),
            'refresh': str(tokens),
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        tokens = RefreshToken.for_user(user)
        return Response({
            'access': str(tokens.access_token),
            'refresh': str(tokens),
            'user': UserSerializer(user).data,
        })


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserSerializer(request.user).data)


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        old_password = request.data.get('old_password', '')
        new_password = request.data.get('new_password', '')

        if not old_password or not new_password:
            return Response(
                {'detail': 'Podaj stare i nowe hasło.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(old_password):
            return Response(
                {'old_password': 'Nieprawidłowe aktualne hasło.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 8:
            return Response(
                {'new_password': 'Nowe hasło musi mieć co najmniej 8 znaków.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.set_password(new_password)
        request.user.save()
        return Response({'detail': 'Hasło zostało zmienione.'})


class AccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)


class AccountDetailView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user)

from django.db import transaction
from cards.services import CardIntegrationService
from transfers.models import Transfer

class JuniorListView(generics.ListCreateAPIView):
    serializer_class = JuniorProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JuniorProfile.objects.filter(parent=self.request.user)

    def post(self, request, *args, **kwargs):
        serializer = JuniorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        with transaction.atomic():
            data = serializer.validated_data
            email = data['email']
            password = data['password']
            first_name = data.get('first_name', '')
            last_name = data.get('last_name', '')
            pesel = data.get('pesel', '')
            daily_limit = data.get('daily_limit', 100.00)
            blik_limit = data.get('blik_limit', 50.00)
            
            user = request.user.__class__(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                pesel=pesel,
            )
            user.set_password(password)
            user.save()
            
            profile = JuniorProfile.objects.create(
                user=user,
                parent=request.user,
                daily_limit=daily_limit,
                blik_limit=blik_limit
            )
            
            parent_account = request.user.accounts.first()
            
            account = Account.objects.create(
                user=user,
                iban=Account.generate_iban(),
                account_type=Account.AccountType.JUNIOR,
                parent_account=parent_account,
                balance=0,
            )
            
            card_service = CardIntegrationService()
            card_service.order_card(account, card_type="PREPAID", initial_balance=0.0)

        return Response(JuniorProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

class JuniorDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = JuniorProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return JuniorProfile.objects.filter(parent=self.request.user)


class JuniorTopUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            profile = JuniorProfile.objects.get(pk=pk, parent=request.user)
        except JuniorProfile.DoesNotExist:
            return Response({'detail': 'Konto Junior nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except Exception:
            return Response({'amount': 'Nieprawidłowa kwota.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'amount': 'Kwota musi być większa od zera.'}, status=status.HTTP_400_BAD_REQUEST)

        parent_account = request.user.accounts.filter(account_type=Account.AccountType.CHECKING).first() \
                         or request.user.accounts.first()
        if not parent_account:
            return Response({'detail': 'Nie znaleziono konta rodzica.'}, status=status.HTTP_404_NOT_FOUND)

        if parent_account.available_balance < amount:
            return Response({'amount': 'Niewystarczające środki na koncie.'}, status=status.HTTP_400_BAD_REQUEST)

        child_account = Account.objects.filter(user=profile.user, account_type=Account.AccountType.JUNIOR).first()
        if not child_account:
            return Response({'detail': 'Konto Junior dziecka nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            locked_parent = Account.objects.select_for_update().get(pk=parent_account.pk)
            if locked_parent.available_balance < amount:
                return Response({'amount': 'Niewystarczające środki na koncie.'}, status=status.HTTP_400_BAD_REQUEST)
            locked_child = Account.objects.select_for_update().get(pk=child_account.pk)
            locked_parent.balance -= amount
            locked_child.balance += amount
            locked_parent.save(update_fields=['balance'])
            locked_child.save(update_fields=['balance'])
            Transfer.objects.create(
                sender_account=locked_parent,
                recipient_iban=locked_child.iban,
                recipient_name=f"{profile.user.first_name} {profile.user.last_name} (Junior)",
                amount=amount,
                title=f"Kieszonkowe dla {profile.user.first_name}",
                system_route='INTERNAL',
                status='COMPLETED',
            )

        return Response({
            'detail': f'Przelano {amount} PLN na konto {profile.user.first_name}.',
            'amount': str(amount),
            'new_child_balance': str(locked_child.balance),
        })


class JuniorCardTopUpView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            profile = JuniorProfile.objects.get(pk=pk, parent=request.user)
        except JuniorProfile.DoesNotExist:
            return Response({'detail': 'Konto Junior nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except Exception:
            return Response({'amount': 'Nieprawidłowa kwota.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'amount': 'Kwota musi być większa od zera.'}, status=status.HTTP_400_BAD_REQUEST)

        parent_account = request.user.accounts.filter(account_type=Account.AccountType.CHECKING).first() \
                         or request.user.accounts.first()
        if not parent_account:
            return Response({'detail': 'Nie znaleziono konta rodzica.'}, status=status.HTTP_404_NOT_FOUND)

        if parent_account.available_balance < amount:
            return Response({'amount': 'Niewystarczające środki na koncie.'}, status=status.HTTP_400_BAD_REQUEST)

        child_account = Account.objects.filter(user=profile.user, account_type=Account.AccountType.JUNIOR).first()
        if not child_account:
            return Response({'detail': 'Konto Junior dziecka nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        child_card = child_account.cards.first()
        if not child_card:
            return Response({'detail': 'Brak karty prepaid przypisanej do konta dziecka.'}, status=status.HTTP_404_NOT_FOUND)

        from cards.services import CardIntegrationService
        card_service = CardIntegrationService()

        details = card_service.get_card_details(child_card.external_card_id)
        card_status = details.get('status') if details.get('success') else None
        if card_status and card_status != 'ACTIVE':
            return Response(
                {'detail': f'Karta dziecka ma status "{card_status}" i nie może być doładowana. Aktywuj kartę w panelu administratora kart.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = card_service.topup_prepaid(card_token=child_card.external_card_id, amount=amount)
        if not result.get('success'):
            return Response({'detail': result.get('details', 'Błąd doładowania karty.')}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            locked = Account.objects.select_for_update().get(pk=parent_account.pk)
            if locked.available_balance < amount:
                return Response({'amount': 'Niewystarczające środki na koncie.'}, status=status.HTTP_400_BAD_REQUEST)
            locked.balance -= amount
            locked.save(update_fields=['balance'])
            Transfer.objects.create(
                sender_account=locked,
                recipient_iban=child_account.iban,
                recipient_name=f"{profile.user.first_name} {profile.user.last_name} (Karta Junior)",
                amount=amount,
                title=f"Doładowanie karty prepaid – {profile.user.first_name}",
                system_route='INTERNAL',
                status='COMPLETED',
            )

        return Response({
            'detail': f'Karta {profile.user.first_name} została doładowana.',
            'new_card_balance': result.get('new_balance'),
            'amount': str(amount),
        })


class AccountBalanceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            account = Account.objects.get(pk=pk, user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            'balance': account.balance,
            'blocked_funds': account.blocked_funds,
            'available_balance': account.available_balance,
        })


class TopUpView(APIView):
    """Doładowanie konta – wyłącznie do celów testowych."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            account = Account.objects.get(pk=pk, user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            amount = Decimal(str(request.data.get('amount', 0)))
        except Exception:
            return Response({'amount': 'Nieprawidłowa kwota.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'amount': 'Kwota musi być większa od zera.'}, status=status.HTTP_400_BAD_REQUEST)

        account.balance += amount
        account.save()
        return Response(AccountSerializer(account).data)


class SetBlikPinView(APIView):
    """Ustawienie 4-cyfrowego kodu PIN dla transakcji BLIK."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import django.contrib.auth.hashers as hashers
        pin = request.data.get('pin', '').strip()

        if not pin or len(pin) != 4 or not pin.isdigit():
            return Response(
                {'pin': 'PIN musi składać się z dokładnie 4 cyfr.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        request.user.blik_pin = hashers.make_password(pin)
        request.user.save(update_fields=['blik_pin'])
        return Response({'detail': 'PIN BLIK został poprawnie ustawiony.'})


# ─── Przelewy Junior ────────────────────────────────────────────────────────

class JuniorTransferRequestCreateView(APIView):
    """Junior tworzy wniosek o przelew — wymaga zatwierdzenia przez rodzica."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            junior_profile = request.user.junior_profile
        except JuniorProfile.DoesNotExist:
            return Response({'detail': 'Tylko konto Junior może wysyłać wnioski.'}, status=status.HTTP_403_FORBIDDEN)

        junior_account = Account.objects.filter(
            user=request.user, account_type=Account.AccountType.JUNIOR
        ).first()
        if not junior_account:
            return Response({'detail': 'Brak konta Junior.'}, status=status.HTTP_404_NOT_FOUND)

        parent_account = Account.objects.filter(user=junior_profile.parent).first()
        if not parent_account:
            return Response({'detail': 'Brak konta rodzica.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = JuniorTransferRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            amount = Decimal(str(serializer.validated_data['amount']))
        except Exception:
            return Response({'amount': 'Nieprawidłowa kwota.'}, status=status.HTTP_400_BAD_REQUEST)

        if amount <= 0:
            return Response({'amount': 'Kwota musi być większa od zera.'}, status=status.HTTP_400_BAD_REQUEST)

        if junior_account.available_balance < amount:
            return Response({'amount': 'Niewystarczające środki na koncie.'}, status=status.HTTP_400_BAD_REQUEST)

        req = JuniorTransferRequest.objects.create(
            junior_account=junior_account,
            parent_account=parent_account,
            amount=amount,
            recipient_iban=serializer.validated_data['recipient_iban'],
            recipient_name=serializer.validated_data['recipient_name'],
            title=serializer.validated_data['title'],
        )
        return Response(JuniorTransferRequestSerializer(req).data, status=status.HTTP_201_CREATED)


class JuniorTransferRequestListView(generics.ListAPIView):
    """Junior widzi listę swoich wniosków."""
    serializer_class = JuniorTransferRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        junior_account = Account.objects.filter(
            user=self.request.user, account_type=Account.AccountType.JUNIOR
        ).first()
        if not junior_account:
            return JuniorTransferRequest.objects.none()
        return JuniorTransferRequest.objects.filter(junior_account=junior_account)


class ParentTransferRequestListView(generics.ListAPIView):
    """Rodzic widzi wnioski przelewowe od swoich dzieci."""
    serializer_class = JuniorTransferRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent_account = Account.objects.filter(user=self.request.user).first()
        if not parent_account:
            return JuniorTransferRequest.objects.none()
        return JuniorTransferRequest.objects.filter(
            parent_account=parent_account, status=JuniorTransferRequest.Status.PENDING
        )


class ParentTransferRequestApproveView(APIView):
    """Rodzic zatwierdza wniosek — wykonuje przelew ze środków dziecka."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        try:
            req = JuniorTransferRequest.objects.select_related(
                'junior_account', 'parent_account'
            ).get(pk=pk, parent_account__user=request.user, status=JuniorTransferRequest.Status.PENDING)
        except JuniorTransferRequest.DoesNotExist:
            return Response({'detail': 'Wniosek nie istnieje lub już został rozpatrzony.'}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            locked_junior = Account.objects.select_for_update().get(pk=req.junior_account.pk)
            if locked_junior.available_balance < req.amount:
                return Response({'detail': 'Dziecko nie ma wystarczających środków.'}, status=status.HTTP_400_BAD_REQUEST)

            locked_junior.balance -= req.amount
            locked_junior.save(update_fields=['balance'])

            Transfer.objects.create(
                sender_account=locked_junior,
                recipient_iban=req.recipient_iban,
                recipient_name=req.recipient_name,
                amount=req.amount,
                title=req.title,
                system_route='INTERNAL',
                status='COMPLETED',
            )

            req.status = JuniorTransferRequest.Status.APPROVED
            req.reviewed_at = timezone.now()
            req.save(update_fields=['status', 'reviewed_at'])

        return Response({'detail': 'Przelew zatwierdzony i wykonany.'})


class ParentTransferRequestRejectView(APIView):
    """Rodzic odrzuca wniosek."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        try:
            req = JuniorTransferRequest.objects.get(
                pk=pk, parent_account__user=request.user, status=JuniorTransferRequest.Status.PENDING
            )
        except JuniorTransferRequest.DoesNotExist:
            return Response({'detail': 'Wniosek nie istnieje lub już został rozpatrzony.'}, status=status.HTTP_404_NOT_FOUND)

        req.status = JuniorTransferRequest.Status.REJECTED
        req.reviewed_at = timezone.now()
        req.save(update_fields=['status', 'reviewed_at'])

        return Response({'detail': 'Wniosek odrzucony.'})
