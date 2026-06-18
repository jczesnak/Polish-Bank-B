from decimal import Decimal

from rest_framework import serializers
from .models import BlikCode, BlikTransaction, PhoneAlias, P2pContact


class BlikGenerateSerializer(serializers.Serializer):
    account_id = serializers.UUIDField()


class BlikWebhookSerializer(serializers.Serializer):
    transaction_id = serializers.UUIDField()
    # KLIK nie przekazuje user_id w webhooku autoryzacyjnym (patrz codes/tasks.py).
    # Korelujemy transakcję z aktywnym kodem BLIK po stronie banku.
    user_id = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    currency = serializers.CharField(max_length=3, default='PLN')
    merchant_name = serializers.CharField(max_length=200, required=False, allow_blank=True, default='')
    is_on_us = serializers.BooleanField(required=False, default=False)
    expiry_time = serializers.DateTimeField(required=False)
    zone = serializers.CharField(max_length=2, required=False, default='PL')


class BlikPingSerializer(serializers.Serializer):
    timestamp = serializers.DateTimeField()
    nonce = serializers.CharField()


class BlikTransactionSerializer(serializers.ModelSerializer):
    junior_user_name = serializers.SerializerMethodField()

    class Meta:
        model = BlikTransaction
        fields = [
            'id', 'klik_transaction_id', 'amount', 'currency',
            'merchant_name', 'status', 'reject_reason', 'created_at', 'completed_at',
            'needs_parent_auth', 'junior_user_name',
        ]
        read_only_fields = fields

    def get_junior_user_name(self, obj):
        if obj.needs_parent_auth:
            return obj.user.first_name
        return None


# --- P2P (przelew na telefon) --------------------------------------------

class PhoneAliasSerializer(serializers.ModelSerializer):
    account_iban = serializers.CharField(source='account.iban', read_only=True)

    class Meta:
        model = PhoneAlias
        fields = ['id', 'phone', 'account', 'account_iban', 'klik_alias_id', 'zone', 'created_at']
        read_only_fields = ['id', 'klik_alias_id', 'zone', 'created_at', 'account_iban']


class RegisterAliasSerializer(serializers.Serializer):
    """Rejestracja własnego numeru telefonu jako aliasu P2P.

    `phone` opcjonalny — domyślnie bierzemy numer z profilu użytkownika.
    """
    account_id = serializers.UUIDField()
    phone = serializers.CharField(max_length=16, required=False, allow_blank=True, default='')


class P2pContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = P2pContact
        fields = ['id', 'name', 'phone', 'created_at']
        read_only_fields = ['id', 'created_at']


class P2PTransferSerializer(serializers.Serializer):
    """Przelew na telefon: bank pyta KLIK o IBAN odbiorcy i realizuje przelew."""
    sender_account = serializers.UUIDField()
    recipient_phone = serializers.CharField(max_length=16)
    recipient_name = serializers.CharField(max_length=120, required=False, allow_blank=True, default='')
    save_contact = serializers.BooleanField(required=False, default=False)
    amount = serializers.DecimalField(max_digits=15, decimal_places=2, min_value=Decimal('0.01'))
    title = serializers.CharField(max_length=255, required=False, allow_blank=True, default='Przelew na telefon')
