import random
import uuid

from django.db import models

from accounts.models import Account, User


class PrepaidCard(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Aktywna'
        BLOCKED = 'BLOCKED', 'Zablokowana'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='prepaid_cards')
    account = models.OneToOneField(Account, on_delete=models.CASCADE, related_name='prepaid_card')
    masked_number = models.CharField(max_length=19, unique=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    daily_limit = models.DecimalField(max_digits=15, decimal_places=2, default=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'prepaid_cards'

    def __str__(self):
        return f'{self.masked_number} ({self.owner.email})'

    @staticmethod
    def generate_masked_number():
        suffix = ''.join(str(random.randint(0, 9)) for _ in range(4))
        return f'5321 **** **** {suffix}'


class CardTransaction(models.Model):
    class TransactionType(models.TextChoices):
        INTERNET = 'INTERNET', 'Płatność internetowa'
        POS = 'POS', 'Płatność kartą'

    class Status(models.TextChoices):
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Oczekuje na zgodę rodzica'
        COMPLETED = 'COMPLETED', 'Zrealizowana'
        REJECTED = 'REJECTED', 'Odrzucona'
        FAILED = 'FAILED', 'Nieudana'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card = models.ForeignKey(PrepaidCard, on_delete=models.PROTECT, related_name='transactions')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='card_transactions')
    merchant_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    transaction_type = models.CharField(
        max_length=20, choices=TransactionType.choices, default=TransactionType.INTERNET
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING_APPROVAL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'card_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.merchant_name} {self.amount} PLN [{self.status}]'
