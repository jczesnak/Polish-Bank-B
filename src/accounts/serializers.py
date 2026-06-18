from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Account, JuniorTransferRequest


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['pesel', 'first_name', 'last_name', 'email', 'phone_number', 'password', 'password_confirm']

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Hasła nie są identyczne.'})
        pesel = data.get('pesel', '')
        if pesel and (not pesel.isdigit() or len(pesel) != 11):
            raise serializers.ValidationError({'pesel': 'PESEL musi składać się z 11 cyfr.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        email = validated_data['email']
        user = User(username=email, **validated_data)
        user.set_password(password)
        user.save()
        Account.objects.create(
            user=user,
            iban=Account.generate_iban(),
            account_type=Account.AccountType.CHECKING,
            balance=0,
        )
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(
            request=self.context.get('request'),
            username=data['email'],
            password=data['password'],
        )
        if not user:
            raise serializers.ValidationError('Nieprawidłowy email lub hasło.')
        if not user.is_active:
            raise serializers.ValidationError('Konto jest nieaktywne.')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    is_junior = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'pesel', 'is_junior']
        read_only_fields = ['id']

    def get_is_junior(self, obj):
        return hasattr(obj, 'junior_profile')


import datetime
from .models import JuniorProfile

def get_birth_date_from_pesel(pesel: str) -> datetime.date:
    year = int(pesel[0:2])
    month = int(pesel[2:4])
    day = int(pesel[4:6])

    if 81 <= month <= 92:
        year += 1800
        month -= 80
    elif 1 <= month <= 12:
        year += 1900
    elif 21 <= month <= 32:
        year += 2000
        month -= 20
    elif 41 <= month <= 52:
        year += 2100
        month -= 40
    elif 61 <= month <= 72:
        year += 2200
        month -= 60
    
    return datetime.date(year, month, day)

def get_age(birth_date: datetime.date) -> int:
    today = datetime.date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

class JuniorCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    daily_limit = serializers.DecimalField(max_digits=10, decimal_places=2, default=100.00, required=False)
    blik_limit = serializers.DecimalField(max_digits=10, decimal_places=2, default=50.00, required=False)

    class Meta:
        model = User
        fields = ['pesel', 'first_name', 'last_name', 'email', 'password', 'daily_limit', 'blik_limit']

    def validate_pesel(self, value):
        if not value or not value.isdigit() or len(value) != 11:
            raise serializers.ValidationError('PESEL musi składać się z 11 cyfr.')
        
        try:
            birth_date = get_birth_date_from_pesel(value)
        except ValueError:
            raise serializers.ValidationError('Nieprawidłowy numer PESEL.')
            
        age = get_age(birth_date)
        if age >= 12:
            raise serializers.ValidationError(f'Konto Junior może zostać założone tylko dla dzieci poniżej 12 roku życia. Wyliczony wiek: {age} lat.')
            
        return value

class JuniorProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    account_id = serializers.SerializerMethodField()
    account_balance = serializers.SerializerMethodField()
    prepaid_card_id = serializers.SerializerMethodField()
    prepaid_card_masked_number = serializers.SerializerMethodField()
    prepaid_card_status = serializers.SerializerMethodField()

    class Meta:
        model = JuniorProfile
        fields = ['id', 'user', 'daily_limit', 'blik_limit', 'account_id', 'account_balance', 'prepaid_card_id', 'prepaid_card_masked_number', 'prepaid_card_status']

    def _get_junior_account(self, obj):
        return obj.user.accounts.filter(account_type='JUNIOR').first()

    def get_account_id(self, obj):
        account = self._get_junior_account(obj)
        return str(account.id) if account else None

    def get_account_balance(self, obj):
        account = self._get_junior_account(obj)
        return str(account.balance) if account else '0.00'

    def get_prepaid_card_id(self, obj):
        account = self._get_junior_account(obj)
        if account:
            card = account.cards.first()
            return card.id if card else None
        return None

    def get_prepaid_card_masked_number(self, obj):
        account = self._get_junior_account(obj)
        if account:
            card = account.cards.first()
            return card.masked_number if card else None
        return None

    def get_prepaid_card_status(self, obj):
        account = self._get_junior_account(obj)
        if account:
            card = account.cards.first()
            if card:
                try:
                    from cards.services import CardIntegrationService
                    details = CardIntegrationService().get_card_details(card.external_card_id)
                    return details.get('status') if details.get('success') else None
                except Exception:
                    return None
        return None


class JuniorTransferRequestSerializer(serializers.ModelSerializer):
    junior_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = JuniorTransferRequest
        fields = [
            'id', 'amount', 'recipient_iban', 'recipient_name', 'title',
            'status', 'status_display', 'created_at', 'reviewed_at', 'junior_name',
        ]
        read_only_fields = ['id', 'status', 'created_at', 'reviewed_at']

    def get_junior_name(self, obj):
        u = obj.junior_account.user
        return f"{u.first_name} {u.last_name}"


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']


class AccountSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)

    class Meta:
        model = Account
        fields = [
            'id', 'iban', 'balance', 'blocked_funds', 'available_balance',
            'currency', 'account_type', 'account_type_display', 'created_at',
        ]
        read_only_fields = ['id', 'iban', 'created_at']
