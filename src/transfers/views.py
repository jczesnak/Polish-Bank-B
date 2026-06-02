# src/transfers/views.py
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from cards.models import CardTransaction
from blik.models import BlikTransaction
from blik.payments import accept_blik_transaction, reject_blik_transaction, BlikPaymentError
from .models import ApprovalRequest, Transfer

from .notifications import send_user_event
from .serializers import ApprovalRequestSerializer, TransferSerializer, InternalTransferSerializer
from accounts.models import Account


class IncomingTransferListView(generics.ListAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_ibans = Account.objects.filter(user=self.request.user).values_list('iban', flat=True)
        return Transfer.objects.filter(recipient_iban__in=user_ibans).order_by('-created_at')


class TransferListCreateView(generics.ListCreateAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):

        return Transfer.objects.filter(sender_account__user=self.request.user)
        
    def perform_create(self, serializer):

        serializer.save()

class TransferDetailView(generics.RetrieveAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)

class InternalTransferView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = InternalTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        sender_account = data['sender_account']
        recipient_iban = data['recipient_iban']
        amount = data['amount']

        try:

            sender = Account.objects.select_for_update().get(id=sender_account.id)
            receiver = Account.objects.select_for_update().get(iban=recipient_iban)
        except Account.DoesNotExist:
            return Response(
                {"recipient_iban": "Nie znaleziono rachunku odbiorcy w naszym banku. Użyj przelewu zewnętrznego."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        if sender.id == receiver.id:
            return Response(
                {"error": "Nie można wykonać przelewu na ten sam rachunek."}, 
                status=status.HTTP_400_BAD_REQUEST
            )


        is_junior = sender.account_type == Account.AccountType.JUNIOR
        transfer = Transfer.objects.create(
            sender_account=sender,
            recipient_iban=recipient_iban,
            recipient_name=data.get('recipient_name', ''),
            amount=amount,
            title=data.get('title', ''),
            system_route='INTERNAL',
            status=Transfer.Status.PENDING_APPROVAL if is_junior else Transfer.Status.COMPLETED,
            processed_at=None if is_junior else timezone.now(),
        )

        if is_junior:
            parent = sender.parent_account.user
            approval = ApprovalRequest.objects.create(
                request_type=ApprovalRequest.RequestType.TRANSFER,
                junior=request.user,
                parent=parent,
                account=sender,
                transfer=transfer,
            )
            send_user_event(parent.id, 'approval.created', {
                'approval_id': str(approval.id),
                'type': approval.request_type,
                'junior_name': f'{request.user.first_name} {request.user.last_name}'.strip(),
                'amount': str(transfer.amount),
                'target': transfer.recipient_name or transfer.recipient_iban,
            })
            return Response(
                {
                    "message": "Przelew oczekuje na zgodę rodzica.",
                    "transfer_id": transfer.id,
                    "approval_id": approval.id,
                    "status": transfer.status,
                    "amount": transfer.amount,
                },
                status=status.HTTP_202_ACCEPTED,
            )

        sender.balance -= amount
        receiver.balance += amount

        sender.save()
        receiver.save()

        return Response(
            {
                "message": "Przelew wewnętrzny został zrealizowany natychmiastowo.", 
                "transfer_id": transfer.id,
                "status": transfer.status,
                "amount": transfer.amount
            },
            status=status.HTTP_201_CREATED
        )


class ApprovalListView(generics.ListAPIView):
    serializer_class = ApprovalRequestSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ApprovalRequest.objects.filter(parent=self.request.user).select_related(
            'junior', 'account', 'transfer', 'card_transaction', 'blik_transaction'
        )


class ApprovalDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk, decision):
        try:
            approval = ApprovalRequest.objects.select_for_update().get(
                pk=pk, parent=request.user
            )
        except ApprovalRequest.DoesNotExist:
            return Response({'detail': 'Wniosek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        if approval.status != ApprovalRequest.Status.PENDING:
            return Response({'detail': 'Ten wniosek został już rozpatrzony.'}, status=status.HTTP_400_BAD_REQUEST)

        if decision == 'reject':
            self._reject(approval)
            send_user_event(approval.junior_id, 'approval.rejected', ApprovalRequestSerializer(approval).data)
            return Response(ApprovalRequestSerializer(approval).data)

        result = self._approve(approval)
        if isinstance(result, Response):
            return result
        send_user_event(approval.junior_id, 'approval.approved', ApprovalRequestSerializer(approval).data)
        return Response(ApprovalRequestSerializer(approval).data)

    def _reject(self, approval):
        approval.status = ApprovalRequest.Status.REJECTED
        approval.decided_at = timezone.now()
        approval.save(update_fields=['status', 'decided_at'])
        if approval.transfer_id:
            transfer = Transfer.objects.select_for_update().get(pk=approval.transfer_id)
            transfer.status = Transfer.Status.REJECTED
            transfer.processed_at = timezone.now()
            transfer.save(update_fields=['status', 'processed_at'])
        if approval.card_transaction_id:
            card_tx = CardTransaction.objects.select_for_update().get(pk=approval.card_transaction_id)
            card_tx.status = CardTransaction.Status.REJECTED
            card_tx.processed_at = timezone.now()
            card_tx.save(update_fields=['status', 'processed_at'])
        if approval.blik_transaction_id:
            blik_tx = BlikTransaction.objects.select_for_update().get(pk=approval.blik_transaction_id)
            try:
                reject_blik_transaction(blik_tx)
            except BlikPaymentError:
                pass

    def _approve(self, approval):
        account = Account.objects.select_for_update().get(pk=approval.account_id)
        if approval.transfer_id:
            transfer = Transfer.objects.select_for_update().get(pk=approval.transfer_id)
            amount = transfer.amount
        elif approval.card_transaction_id:
            card_tx = CardTransaction.objects.select_for_update().get(pk=approval.card_transaction_id)
            amount = card_tx.amount
        elif approval.blik_transaction_id:
            blik_tx = BlikTransaction.objects.select_for_update().get(pk=approval.blik_transaction_id)
            amount = blik_tx.amount
        else:
            return Response({'detail': 'Nieprawidłowy wniosek.'}, status=status.HTTP_400_BAD_REQUEST)

        if approval.blik_transaction_id:
            return self._approve_blik(approval, blik_tx)

        if account.available_balance < amount:
            return Response({'amount': 'Niewystarczające środki na rachunku juniora.'}, status=status.HTTP_400_BAD_REQUEST)

        if approval.transfer_id:
            account.balance -= transfer.amount
            receiver = Account.objects.select_for_update().filter(iban=transfer.recipient_iban).first()
            if receiver is not None:
                receiver.balance += transfer.amount
                receiver.save(update_fields=['balance'])
            account.save(update_fields=['balance'])
            transfer.status = Transfer.Status.COMPLETED
            transfer.processed_at = timezone.now()
            transfer.save(update_fields=['status', 'processed_at'])

        if approval.card_transaction_id:
            account.balance -= card_tx.amount
            account.save(update_fields=['balance'])
            card_tx.status = CardTransaction.Status.COMPLETED
            card_tx.processed_at = timezone.now()
            card_tx.save(update_fields=['status', 'processed_at'])

        approval.status = ApprovalRequest.Status.APPROVED
        approval.decided_at = timezone.now()
        approval.save(update_fields=['status', 'decided_at'])
        return approval

    def _approve_blik(self, approval, blik_tx):
        try:
            accept_blik_transaction(blik_tx)
        except BlikPaymentError as exc:
            return Response({'detail': exc.message}, status=exc.http_status)

        approval.status = ApprovalRequest.Status.APPROVED
        approval.decided_at = timezone.now()
        approval.save(update_fields=['status', 'decided_at'])
        return approval