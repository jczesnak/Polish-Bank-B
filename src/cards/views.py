from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from transfers.models import ApprovalRequest
from transfers.notifications import send_user_event
from .models import CardTransaction, PrepaidCard
from .serializers import CardPaymentSerializer, CardTransactionSerializer, PrepaidCardSerializer


class PrepaidCardListView(generics.ListAPIView):
    serializer_class = PrepaidCardSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PrepaidCard.objects.filter(owner=self.request.user).select_related('account')


class CardTransactionListView(generics.ListAPIView):
    serializer_class = CardTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CardTransaction.objects.filter(card__owner=self.request.user).select_related('card', 'account')


class CardPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, card_id):
        serializer = CardPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            card = PrepaidCard.objects.select_related('account', 'account__parent_account').get(
                pk=card_id, owner=request.user, status=PrepaidCard.Status.ACTIVE
            )
        except PrepaidCard.DoesNotExist:
            return Response({'detail': 'Karta nie istnieje albo jest nieaktywna.'}, status=status.HTTP_404_NOT_FOUND)

        account = Account.objects.select_for_update().get(pk=card.account_id)
        if account.available_balance < data['amount']:
            return Response({'amount': 'Niewystarczające środki na rachunku.'}, status=status.HTTP_400_BAD_REQUEST)

        tx_status = CardTransaction.Status.PENDING_APPROVAL
        processed_at = None
        if account.account_type != Account.AccountType.JUNIOR:
            account.balance -= data['amount']
            account.save(update_fields=['balance'])
            tx_status = CardTransaction.Status.COMPLETED
            processed_at = timezone.now()

        card_tx = CardTransaction.objects.create(
            card=card,
            account=account,
            merchant_name=data['merchant_name'],
            amount=data['amount'],
            transaction_type=data['transaction_type'],
            status=tx_status,
            processed_at=processed_at,
        )

        approval = None
        if account.account_type == Account.AccountType.JUNIOR:
            parent = account.parent_account.user
            approval = ApprovalRequest.objects.create(
                request_type=ApprovalRequest.RequestType.CARD_PAYMENT,
                junior=request.user,
                parent=parent,
                account=account,
                card_transaction=card_tx,
            )
            send_user_event(parent.id, 'approval.created', {
                'approval_id': str(approval.id),
                'type': approval.request_type,
                'junior_name': f'{request.user.first_name} {request.user.last_name}'.strip(),
                'amount': str(card_tx.amount),
                'target': card_tx.merchant_name,
            })

        http_status = status.HTTP_202_ACCEPTED if approval else status.HTTP_201_CREATED
        return Response(
            {
                'transaction': CardTransactionSerializer(card_tx).data,
                'approval_id': str(approval.id) if approval else None,
                'message': 'Płatność oczekuje na zgodę rodzica.' if approval else 'Płatność zrealizowana.',
            },
            status=http_status,
        )
