from decimal import Decimal

from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Account
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    AccountSerializer, UpdateProfileSerializer,
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
