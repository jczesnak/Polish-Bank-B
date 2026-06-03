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