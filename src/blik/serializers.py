from rest_framework import serializers
from .models import BlikCode, BlikTransaction


class BlikGenerateSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()


class BlikWebhookSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    user_id = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value='0.01')
    currency = serializers.CharField(max_length=3, default='PLN')
    merchant_name = serializers.CharField(max_length=200, required=False, default='')
    is_on_us = serializers.BooleanField(required=False, default=False)
    expiry_time = serializers.DateTimeField(required=False)
    zone = serializers.CharField(max_length=2, required=False, default='PL')


class BlikPingSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    nonce = serializers.CharField()


class BlikTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlikTransaction
        fields = [
            'id', 'klik_transaction_id', 'amount', 'currency',
            'merchant_name', 'status', 'reject_reason', 'created_at', 'completed_at',
        ]
        read_only_fields = fields
