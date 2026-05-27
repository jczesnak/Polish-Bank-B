from decimal import Decimal

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from .models import BlikCode, BlikTransaction
from .serializers import BlikGenerateSerializer, BlikWebhookSerializer, BlikPingSerializer, BlikTransactionSerializer
from .services import KlikService


class BlikGenerateView(APIView):
    """Generuje 6-cyfrowy kod BLIK dla zalogowanego klienta."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BlikGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data['account_id']
        try:
            account = Account.objects.get(pk=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = KlikService().generate_code(user_id=str(request.user.id))
        except Exception as exc:
            return Response(
                {'detail': f'Błąd komunikacji z systemem BLIK: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        BlikCode.objects.create(
            user=request.user,
            account=account,
            code=result['code'],
            expires_at=parse_datetime(result['expires_at']),
        )

        return Response({
            'code': result['code'],
            'expires_at': result['expires_at'],
            'expires_in': result.get('expires_in', 120),
        })


class BlikWebhookAuthorizeView(APIView):
    """
    Webhook wywoływany przez KLIK gdy merchant inicjuje płatność.
    Bank sprawdza środki, zakłada blokadę i wywołuje /payments/confirm do KLIK.
    Odpowiedź 200 potwierdza tylko odbiór — decyzja idzie przez /payments/confirm.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BlikWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            blik_code = BlikCode.objects.filter(
                user__id=data['user_id'],
                status=BlikCode.Status.ACTIVE,
                expires_at__gt=timezone.now(),
            ).latest('created_at')
        except BlikCode.DoesNotExist:
            return Response({'detail': 'Brak aktywnego kodu BLIK.'}, status=status.HTTP_404_NOT_FOUND)

        account = blik_code.account
        amount = Decimal(str(data['amount']))

        if account.available_balance < amount:
            self._reject(data['transaction_id'], 'INSUFFICIENT_FUNDS', blik_code, account, data)
            return Response({'received': True, 'will_prompt_user': False})

        # Zablokuj środki przed potwierdzeniem
        account.blocked_funds += amount
        account.save()

        transaction = BlikTransaction.objects.create(
            klik_transaction_id=data['transaction_id'],
            account=account,
            user=blik_code.user,
            amount=amount,
            currency=data['currency'],
            merchant_name=data.get('merchant_name', ''),
        )

        try:
            KlikService().confirm_payment(
                transaction_id=str(data['transaction_id']),
                decision='ACCEPTED',
            )
        except Exception as exc:
            account.blocked_funds -= amount
            account.save()
            transaction.status = BlikTransaction.Status.REJECTED
            transaction.reject_reason = BlikTransaction.RejectReason.OTHER
            transaction.completed_at = timezone.now()
            transaction.save()
            blik_code.status = BlikCode.Status.USED
            blik_code.save()
            return Response(
                {'detail': f'Błąd potwierdzenia w systemie BLIK: {exc}'},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        transaction.status = BlikTransaction.Status.AUTHORIZED
        transaction.save()
        blik_code.status = BlikCode.Status.USED
        blik_code.save()

        return Response({'received': True, 'will_prompt_user': True})

    def _reject(self, transaction_id, reason, blik_code, account, data):
        try:
            KlikService().confirm_payment(
                transaction_id=str(transaction_id),
                decision='REJECTED',
                reject_reason=reason,
            )
        except Exception:
            pass

        BlikTransaction.objects.create(
            klik_transaction_id=transaction_id,
            account=account,
            user=blik_code.user,
            amount=Decimal(str(data['amount'])),
            currency=data['currency'],
            merchant_name=data.get('merchant_name', ''),
            status=BlikTransaction.Status.REJECTED,
            reject_reason=reason,
            completed_at=timezone.now(),
        )
        blik_code.status = BlikCode.Status.USED
        blik_code.save()


class BlikPingView(APIView):
    """Healthcheck wywoływany przez KLIK przy rejestracji webhooka."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BlikPingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            'timestamp': serializer.validated_data['timestamp'],
            'nonce': serializer.validated_data['nonce'],
            'pong': True,
        })


class BlikTransactionListView(generics.ListAPIView):
    serializer_class = BlikTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BlikTransaction.objects.filter(user=self.request.user)
