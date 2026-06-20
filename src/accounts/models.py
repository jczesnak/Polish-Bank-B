import uuid
import random
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    pesel = models.CharField(max_length=11, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=9, blank=True)
    email = models.EmailField(unique=True)
    blik_pin = models.CharField(max_length=128, null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    class Meta:
        db_table = 'users'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.email})"


class Account(models.Model):
    class AccountType(models.TextChoices):
        CHECKING = 'CHECKING', 'Konto osobiste'
        SAVINGS = 'SAVINGS', 'Konto oszczędnościowe'
        JUNIOR = 'JUNIOR', 'Konto Junior'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='accounts')
    iban = models.CharField(max_length=32, unique=True)
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    blocked_funds = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default='PLN')
    account_type = models.CharField(
        max_length=20, choices=AccountType.choices, default=AccountType.CHECKING
    )
    parent_account = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_accounts'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts'

    def __str__(self):
        return f"{self.iban} ({self.user})"

    @property
    def available_balance(self):
        return self.balance - self.blocked_funds

    @staticmethod
    def generate_iban():
   
        bank_code = f"1020{random.randint(1000, 9999)}"
        
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        
        bban = bank_code + account_number
        
        numeric_iban = bban + "252100"
        
        mod = int(numeric_iban) % 97
        check_digits = 98 - mod
        
        check_digits_str = f"{check_digits:02d}"
        
        return f"PL{check_digits_str}{bban}"

class JuniorTransferRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekuje'
        APPROVED = 'APPROVED', 'Zatwierdzone'
        REJECTED = 'REJECTED', 'Odrzucone'

    junior_account = models.ForeignKey(
        'Account', on_delete=models.CASCADE, related_name='transfer_requests'
    )
    parent_account = models.ForeignKey(
        'Account', on_delete=models.CASCADE, related_name='junior_transfer_requests_to_review'
    )
    class SystemRoute(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Wewnętrzny'
        ELIXIR = 'ELIXIR', 'Elixir'
        EXPRESS_ELIXIR = 'EXPRESS_ELIXIR', 'Express Elixir'
        SORBNET = 'SORBNET', 'Sorbnet'

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    recipient_iban = models.CharField(max_length=34)
    recipient_name = models.CharField(max_length=200)
    title = models.CharField(max_length=200)
    system_route = models.CharField(
        max_length=20, choices=SystemRoute.choices, default=SystemRoute.ELIXIR
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'junior_transfer_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.junior_account} → {self.recipient_iban} ({self.amount} PLN) [{self.status}]"


class JuniorProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='junior_profile')
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='children')
    daily_limit = models.DecimalField(max_digits=10, decimal_places=2, default=100.00)
    blik_limit = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)

    class Meta:
        db_table = 'junior_profiles'

    def __str__(self):
        return f"Junior: {self.user.email} (Parent: {self.parent.email})"