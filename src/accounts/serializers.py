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
        fields = ['id', 'email', 'first_name', 'last_name', 'phone_number', 'pesel']
        read_only_fields = ['id']


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
