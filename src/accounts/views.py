from decimal import Decimal

from blik.models import BlikTransaction
from blik.serializers import BlikTransactionSerializer
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from django.db import transaction

from cards.models import CardTransaction, PrepaidCard
from cards.serializers import PrepaidCardSerializer
from transfers.models import Transfer
from .models import Account, User
from .serializers import (
    RegisterSerializer, LoginSerializer, UserSerializer,
    AccountSerializer, UpdateProfileSerializer, JuniorCreateSerializer,
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


class JuniorAccountCreateView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        serializer = JuniorCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        junior = User(
            username=data['email'],
            email=data['email'],
            first_name=data['first_name'],
            last_name=data['last_name'],
            pesel=data['pesel'],
            phone_number=data.get('phone_number', ''),
            role=User.Role.JUNIOR,
        )
        junior.set_password(data['password'])
        junior.save()

        account = Account.objects.create(
            user=junior,
            iban=Account.generate_iban(),
            account_type=Account.AccountType.JUNIOR,
            parent_account=data['parent_account'],
            balance=0,
        )
        PrepaidCard.objects.create(
            owner=junior,
            account=account,
            masked_number=PrepaidCard.generate_masked_number(),
        )

        return Response(
            {'user': UserSerializer(junior).data, 'account': AccountSerializer(account).data},
            status=status.HTTP_201_CREATED,
        )


class JuniorAccountListView(generics.ListAPIView):
    serializer_class = AccountSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        parent_accounts = Account.objects.filter(user=self.request.user)
        return Account.objects.filter(
            account_type=Account.AccountType.JUNIOR,
            parent_account__in=parent_accounts,
        ).select_related('user', 'parent_account')


def _build_junior_activity_payload(junior_account):
    outgoing = Transfer.objects.filter(sender_account=junior_account).order_by('-created_at')
    incoming = Transfer.objects.filter(recipient_iban=junior_account.iban).select_related(
        'sender_account__user'
    ).order_by('-created_at')
    card_transactions = junior_account.card_transactions.all().order_by('-created_at')
    blik_transactions = junior_account.blik_transactions.all().order_by('-created_at')
    prepaid_card = PrepaidCard.objects.filter(account=junior_account).first()

    operations = []

    for transfer in outgoing:
        operations.append({
            'id': str(transfer.id),
            'kind': 'TRANSFER_OUT',
            'direction': 'OUT',
            'title': transfer.title,
            'counterparty': transfer.recipient_name or transfer.recipient_iban,
            'amount': str(transfer.amount),
            'status': transfer.status,
            'status_display': transfer.get_status_display(),
            'category_label': transfer.get_system_route_display(),
            'system_route': transfer.system_route,
            'created_at': transfer.created_at.isoformat(),
            'processed_at': transfer.processed_at.isoformat() if transfer.processed_at else None,
        })

    for transfer in incoming:
        sender_name = (
            f'{transfer.sender_account.user.first_name} {transfer.sender_account.user.last_name}'.strip()
            or transfer.sender_account.iban
        )
        operations.append({
            'id': str(transfer.id),
            'kind': 'TRANSFER_IN',
            'direction': 'IN',
            'title': transfer.title,
            'counterparty': sender_name,
            'amount': str(transfer.amount),
            'status': transfer.status,
            'status_display': transfer.get_status_display(),
            'category_label': transfer.get_system_route_display(),
            'system_route': transfer.system_route,
            'created_at': transfer.created_at.isoformat(),
            'processed_at': transfer.processed_at.isoformat() if transfer.processed_at else None,
        })

    for tx in card_transactions:
        operations.append({
            'id': str(tx.id),
            'kind': 'CARD',
            'direction': 'OUT',
            'title': tx.get_transaction_type_display(),
            'counterparty': tx.merchant_name,
            'amount': str(tx.amount),
            'status': tx.status,
            'status_display': tx.get_status_display(),
            'category_label': 'Karta prepaid',
            'system_route': 'CARD',
            'created_at': tx.created_at.isoformat(),
            'processed_at': tx.processed_at.isoformat() if tx.processed_at else None,
        })

    for tx in blik_transactions:
        operations.append({
            'id': str(tx.id),
            'kind': 'BLIK',
            'direction': 'OUT',
            'title': 'Płatność BLIK',
            'counterparty': tx.merchant_name or 'Sklep',
            'amount': str(tx.amount),
            'status': tx.status,
            'status_display': tx.get_status_display(),
            'category_label': 'BLIK',
            'system_route': 'BLIK',
            'reject_reason': tx.reject_reason,
            'reject_reason_display': tx.get_reject_reason_display() if tx.reject_reason else '',
            'currency': tx.currency,
            'created_at': tx.created_at.isoformat(),
            'processed_at': tx.completed_at.isoformat() if tx.completed_at else None,
        })

    operations.sort(key=lambda item: item['created_at'], reverse=True)
    blik_payload = BlikTransactionSerializer(blik_transactions, many=True).data

    completed_expense_statuses = {
        Transfer.Status.COMPLETED,
        CardTransaction.Status.COMPLETED,
        BlikTransaction.Status.COMPLETED,
    }
    pending_expense_statuses = {
        Transfer.Status.PENDING_APPROVAL,
        Transfer.Status.PENDING,
        CardTransaction.Status.PENDING_APPROVAL,
        BlikTransaction.Status.PENDING,
        BlikTransaction.Status.AUTHORIZED,
    }

    total_expenses = Decimal('0')
    total_income = Decimal('0')
    pending_expenses = Decimal('0')
    expense_count = 0
    income_count = 0
    pending_count = 0

    blik_total = Decimal('0')
    blik_count = len(blik_payload)
    blik_pending = Decimal('0')

    for op in operations:
        amount = Decimal(op['amount'])
        if op['direction'] == 'OUT' and op['status'] in completed_expense_statuses:
            total_expenses += amount
            expense_count += 1
            if op['kind'] == 'BLIK':
                blik_total += amount
        elif op['direction'] == 'OUT' and op['status'] in pending_expense_statuses:
            pending_expenses += amount
            pending_count += 1
            if op['kind'] == 'BLIK':
                blik_pending += amount
        elif op['direction'] == 'IN' and op['status'] == Transfer.Status.COMPLETED:
            total_income += amount
            income_count += 1

    return {
        'account': AccountSerializer(junior_account).data,
        'prepaid_card': PrepaidCardSerializer(prepaid_card).data if prepaid_card else None,
        'summary': {
            'total_expenses': str(total_expenses),
            'total_income': str(total_income),
            'pending_expenses': str(pending_expenses),
            'expense_count': expense_count,
            'income_count': income_count,
            'pending_count': pending_count,
            'operations_count': len(operations),
            'blik_total': str(blik_total),
            'blik_count': blik_count,
            'blik_pending': str(blik_pending),
        },
        'operations': operations,
        'blik_transactions': blik_payload,
    }


class JuniorActivityView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        parent_accounts = Account.objects.filter(user=request.user)
        try:
            junior_account = Account.objects.get(
                pk=pk,
                account_type=Account.AccountType.JUNIOR,
                parent_account__in=parent_accounts,
            )
        except Account.DoesNotExist:
            return Response({'detail': 'Konto juniora nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        return Response(_build_junior_activity_payload(junior_account))


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
