import uuid
import random
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    pesel = models.CharField(max_length=11, unique=True, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True)
    email = models.EmailField(unique=True)

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
        bank_code = "10200000"
        account_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
        check_digits = str(random.randint(10, 99))
        return f"PL{check_digits}{bank_code}{account_number}"
