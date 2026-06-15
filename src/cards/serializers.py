from rest_framework import serializers
from .models import PaymentCard, CardTransaction

class PaymentCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentCard
        fields = ['id', 'card_number', 'external_card_id', 'masked_number', 'is_active', 'created_at']

class CardTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardTransaction
        fields = ['id', 'card', 'amount', 'currency', 'merchant_name', 'status', 'created_at']
