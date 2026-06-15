from django.db import models
from accounts.models import Account

class PaymentCard(models.Model):
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='cards')
    card_number = models.CharField(max_length=19, unique=True)
    external_card_id = models.CharField(max_length=64, unique=True)
    masked_number = models.CharField(max_length=19)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_cards'

    def __str__(self):
        return f"{self.masked_number} - {self.account.account_number}"

class CardTransaction(models.Model):
    class Status(models.TextChoices):
        AUTHORIZED = 'AUTHORIZED', 'Zablokowano środki'
        SETTLED = 'SETTLED', 'Zrealizowana'
        REFUNDED = 'REFUNDED', 'Zwrócona'

    card = models.ForeignKey(PaymentCard, on_delete=models.CASCADE, related_name='transactions')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='PLN')
    merchant_name = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SETTLED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'card_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.card.masked_number} - {self.amount} {self.currency} ({self.status})"