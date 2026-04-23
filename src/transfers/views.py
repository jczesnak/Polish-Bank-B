from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from .models import Transfer
from .serializers import TransferSerializer, CreateTransferSerializer


class TransferListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransferSerializer
        return TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)

    def perform_create(self, serializer):
        transfer = serializer.save(status=Transfer.Status.PENDING)
        account = transfer.sender_account
        account.balance -= transfer.amount
        account.save()


class TransferDetailView(generics.RetrieveAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)
