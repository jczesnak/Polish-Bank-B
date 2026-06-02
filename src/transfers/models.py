import uuid
from django.db import models
from accounts.models import Account


class Transfer(models.Model):
    class TransferSystem(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Wewnętrzny'
        ELIXIR = 'ELIXIR', 'Elixir'
        EXPRESS_ELIXIR = 'EXPRESS_ELIXIR', 'Express Elixir'
        KLIK = 'KLIK', 'KLIK'
        SORBNET = 'SORBNET', 'Sorbnet'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekujący'
        PROCESSING = 'PROCESSING', 'W realizacji'
        COMPLETED = 'COMPLETED', 'Zrealizowany'
        FAILED = 'FAILED', 'Nieudany'
        CANCELLED = 'CANCELLED', 'Anulowany'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender_account = models.ForeignKey(
        Account, on_delete=models.PROTECT, related_name='sent_transfers'
    )
    recipient_iban = models.CharField(max_length=32)
    recipient_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    title = models.CharField(max_length=255)
    system_route = models.CharField(
        max_length=20, choices=TransferSystem.choices, default=TransferSystem.ELIXIR
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'transfers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.system_route} | {self.amount} PLN → {self.recipient_iban}"
