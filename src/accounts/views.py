from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import Account
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, AccountSerializer


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
