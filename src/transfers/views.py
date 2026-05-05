# src/transfers/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Transfer

from .serializers import TransferSerializer, InternalTransferSerializer
from accounts.models import Account


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


        sender.balance -= amount
        receiver.balance += amount

        sender.save()
        receiver.save()


        transfer = Transfer.objects.create(
            sender_account=sender,
            recipient_iban=recipient_iban,
            recipient_name=data.get('recipient_name', ''),
            amount=amount,
            title=data.get('title', ''),
            system_route='INTERNAL',
            status='COMPLETED'
        )

        return Response(
            {
                "message": "Przelew wewnętrzny został zrealizowany natychmiastowo.", 
                "transfer_id": transfer.id,
                "status": transfer.status,
                "amount": transfer.amount
            },
            status=status.HTTP_201_CREATED
        )