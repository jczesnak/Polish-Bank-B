from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Account


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
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'pesel', 'role']
        read_only_fields = ['id']


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number']


class AccountSerializer(serializers.ModelSerializer):
    available_balance = serializers.DecimalField(max_digits=15, decimal_places=2, read_only=True)
    account_type_display = serializers.CharField(source='get_account_type_display', read_only=True)
    parent_account_iban = serializers.CharField(source='parent_account.iban', read_only=True)
    owner_name = serializers.SerializerMethodField(read_only=True)

    def get_owner_name(self, obj):
        return f'{obj.user.first_name} {obj.user.last_name}'.strip()

    class Meta:
        model = Account
        fields = [
            'id', 'iban', 'balance', 'blocked_funds', 'available_balance',
            'currency', 'account_type', 'account_type_display', 'parent_account',
            'parent_account_iban', 'owner_name', 'created_at',
        ]
        read_only_fields = ['id', 'iban', 'created_at']


class JuniorCreateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    pesel = serializers.CharField(max_length=11)
    phone_number = serializers.CharField(max_length=9, required=False, allow_blank=True, default='')
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)
    parent_account_id = serializers.UUIDField()

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Hasła nie są identyczne.'})
        if User.objects.filter(email=data['email']).exists():
            raise serializers.ValidationError({'email': 'Użytkownik z tym adresem email już istnieje.'})
        if User.objects.filter(pesel=data['pesel']).exists():
            raise serializers.ValidationError({'pesel': 'Użytkownik z tym PESEL już istnieje.'})
        if not data['pesel'].isdigit() or len(data['pesel']) != 11:
            raise serializers.ValidationError({'pesel': 'PESEL musi składać się z 11 cyfr.'})

        request = self.context['request']
        try:
            parent_account = Account.objects.get(
                pk=data['parent_account_id'],
                user=request.user,
                account_type__in=[Account.AccountType.CHECKING, Account.AccountType.SAVINGS],
            )
        except Account.DoesNotExist as exc:
            raise serializers.ValidationError(
                {'parent_account_id': 'Konto rodzica nie istnieje albo nie należy do Ciebie.'}
            ) from exc
        data['parent_account'] = parent_account
        return data
