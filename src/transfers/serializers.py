from rest_framework import serializers
from .models import Transfer


class TransferSerializer(serializers.ModelSerializer):
    system_route_display = serializers.CharField(source='get_system_route_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Transfer
        fields = [
            'id', 'sender_account', 'recipient_iban', 'recipient_name',
            'amount', 'title', 'system_route', 'system_route_display',
            'status', 'status_display', 'created_at', 'processed_at',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'processed_at']


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
