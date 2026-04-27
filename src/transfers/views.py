from django.db import transaction
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from accounts.models import Account
from .models import Transfer
from .serializers import TransferSerializer, CreateTransferSerializer


class TransferListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransferSerializer
        return TransferSerializer

    def get_queryset(self):
        from django.db.models import Q
        user_ibans = Account.objects.filter(user=self.request.user).values_list('iban', flat=True)
        return Transfer.objects.filter(
            Q(sender_account__user=self.request.user) |
            Q(recipient_iban__in=user_ibans, system_route=Transfer.TransferSystem.INTERNAL)
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            transfer = serializer.save(status=Transfer.Status.PENDING)
            sender = transfer.sender_account
            sender.balance -= transfer.amount
            sender.save()

            if transfer.system_route == Transfer.TransferSystem.INTERNAL:
                try:
                    recipient = Account.objects.select_for_update().get(
                        iban=transfer.recipient_iban
                    )
                    recipient.balance += transfer.amount
                    recipient.save()
                    transfer.status = Transfer.Status.COMPLETED
                    transfer.save(update_fields=['status'])
                except Account.DoesNotExist:
                    transfer.status = Transfer.Status.FAILED
                    transfer.save(update_fields=['status'])


class TransferDetailView(generics.RetrieveAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)
