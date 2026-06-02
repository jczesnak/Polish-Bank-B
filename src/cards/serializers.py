from decimal import Decimal

from rest_framework import serializers

from .models import CardTransaction, PrepaidCard


class PrepaidCardSerializer(serializers.ModelSerializer):
    account_iban = serializers.CharField(source='account.iban', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = PrepaidCard
        fields = [
            'id', 'owner', 'account', 'account_iban', 'masked_number',
            'status', 'status_display', 'daily_limit', 'created_at',
        ]
        read_only_fields = fields


class CardTransactionSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    transaction_type_display = serializers.CharField(source='get_transaction_type_display', read_only=True)

    class Meta:
        model = CardTransaction
        fields = [
            'id', 'card', 'account', 'merchant_name', 'amount', 'transaction_type',
            'transaction_type_display', 'status', 'status_display', 'created_at', 'processed_at',
        ]
        read_only_fields = fields


class CardPaymentSerializer(serializers.Serializer):
    merchant_name = serializers.CharField(max_length=200)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    transaction_type = serializers.ChoiceField(
        choices=CardTransaction.TransactionType.choices,
        default=CardTransaction.TransactionType.INTERNET,
    )
