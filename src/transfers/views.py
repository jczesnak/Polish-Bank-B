# src/transfers/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction

from .models import Transfer

from .serializers import TransferSerializer, InternalTransferSerializer, CreateTransferSerializer
from accounts.models import Account
from .services import ElixirIntegrationService


class IncomingTransferListView(generics.ListAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_ibans = Account.objects.filter(user=self.request.user).values_list('iban', flat=True)
        return Transfer.objects.filter(recipient_iban__in=user_ibans).order_by('-created_at')


class TransferListCreateView(generics.ListCreateAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransferSerializer
        return TransferSerializer

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)
        
    @transaction.atomic
    def perform_create(self, serializer):
        transfer = serializer.save(status='PENDING')
        
        # Jeśli przelew idzie systemem ELIXIR, blokujemy środki i wysyłamy do Elixira
        if transfer.system_route == 'ELIXIR':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save()
            
            try:
                ElixirIntegrationService.send_transfer(transfer)
            except Exception as e:
                raise e
        # Jeśli przelew idzie systemem EXPRESS_ELIXIR, blokujemy środki i wysyłamy do Express Elixira
        elif transfer.system_route == 'EXPRESS_ELIXIR':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save()
            
            try:
                from .services import ExpressElixirIntegrationService
                ExpressElixirIntegrationService.send_transfer(transfer)
            except Exception as e:
                raise e
        elif transfer.system_route == 'SORBNET':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            
            try:
                from .services import SorbnetIntegrationService
                status = SorbnetIntegrationService.send_transfer(transfer)
                
                if status == 'SETTLED':
                    transfer.status = 'COMPLETED'
                    transfer.save()
                    account.balance -= transfer.amount
                    account.save()
                elif status == 'REJECTED':
                    transfer.status = 'FAILED'
                    transfer.save()
                elif status == 'GRIDLOCK_HELD':
                    account.blocked_funds += transfer.amount
                    account.save()
            except Exception as e:
                raise e

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