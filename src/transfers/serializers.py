from rest_framework import serializers
from .models import Transfer


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