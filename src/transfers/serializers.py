from rest_framework import serializers
from .models import ApprovalRequest, Transfer


class TransferSerializer(serializers.ModelSerializer):
    system_route_display = serializers.CharField(source='get_system_route_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    sender_iban = serializers.CharField(source='sender_account.iban', read_only=True)
    sender_name = serializers.SerializerMethodField(read_only=True)

    def get_sender_name(self, obj):
        u = obj.sender_account.user
        return f"{u.first_name} {u.last_name}".strip()

    class Meta:
        model = Transfer
        fields = [
            'id', 'sender_account', 'sender_iban', 'sender_name',
            'recipient_iban', 'recipient_name',
            'amount', 'title', 'system_route', 'system_route_display',
            'status', 'status_display', 'created_at', 'processed_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'processed_at']


class ApprovalRequestSerializer(serializers.ModelSerializer):
    request_type_display = serializers.CharField(source='get_request_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    junior_name = serializers.SerializerMethodField(read_only=True)
    account_iban = serializers.CharField(source='account.iban', read_only=True)
    amount = serializers.SerializerMethodField(read_only=True)
    target = serializers.SerializerMethodField(read_only=True)
    transfer_status = serializers.CharField(source='transfer.status', read_only=True)
    card_transaction_status = serializers.CharField(source='card_transaction.status', read_only=True)
    blik_transaction_status = serializers.CharField(source='blik_transaction.status', read_only=True)

    def get_junior_name(self, obj):
        return f'{obj.junior.first_name} {obj.junior.last_name}'.strip()

    def get_amount(self, obj):
        if obj.transfer_id:
            return str(obj.transfer.amount)
        if obj.card_transaction_id:
            return str(obj.card_transaction.amount)
        if obj.blik_transaction_id:
            return str(obj.blik_transaction.amount)
        return '0.00'

    def get_target(self, obj):
        if obj.transfer_id:
            return obj.transfer.recipient_name or obj.transfer.recipient_iban
        if obj.card_transaction_id:
            return obj.card_transaction.merchant_name
        if obj.blik_transaction_id:
            return obj.blik_transaction.merchant_name or 'Płatność BLIK'
        return ''

    class Meta:
        model = ApprovalRequest
        fields = [
            'id', 'request_type', 'request_type_display', 'status', 'status_display',
            'junior', 'junior_name', 'account', 'account_iban', 'transfer',
            'card_transaction', 'blik_transaction', 'amount', 'target', 'transfer_status',
            'card_transaction_status', 'blik_transaction_status', 'created_at', 'decided_at',
        ]
        read_only_fields = fields


class CreateTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = ['sender_account', 'recipient_iban', 'recipient_name', 'amount', 'title', 'system_route']

    def validate(self, data):
        account = data['sender_account']
        user = self.context['request'].user
        if account.user != user:
            raise serializers.ValidationError({'sender_account': 'Nie masz dostępu do tego rachunku.'})
        if account.available_balance < data['amount']:
            raise serializers.ValidationError({'amount': 'Niewystarczające środki na rachunku.'})
        return data


class InternalTransferSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transfer
        fields = ['sender_account', 'recipient_iban', 'recipient_name', 'amount', 'title']

    def validate(self, data):
        account = data['sender_account']
        user = self.context['request'].user
        

        if account.user != user:
            raise serializers.ValidationError({'sender_account': 'Nie masz dostępu do tego rachunku.'})
        

        if data['amount'] <= 0:
             raise serializers.ValidationError({'amount': 'Kwota przelewu musi być większa niż zero.'})

        dostepne = account.balance - account.blocked_funds 
        
        if dostepne < data['amount']:
            raise serializers.ValidationError({'amount': 'Niewystarczające środki na rachunku (uwzględniając zablokowane środki).'})
            
        return data