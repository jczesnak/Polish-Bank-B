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
        SWIFT = 'SWIFT', 'SWIFT (Międzynarodowy)'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekujący'
        AML_SUSPENDED = 'AML_SUSPENDED', 'Wstrzymany (AML)'
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
    # Pola specyficzne dla SWIFT (GPI)
    swift_uetr = models.UUIDField(null=True, blank=True, help_text='Unique End-to-end Transaction Reference (SWIFT GPI)')
    swift_charge_bearer = models.CharField(
        max_length=4,
        null=True,
        blank=True,
        choices=[('OUR', 'OUR – Pokrywa nadawca'), ('SHA', 'SHA – Dzielone'), ('BEN', 'BEN – Pokrywa odbiorca')],
        help_text='Opcja podziału kosztów SWIFT (ChrgBr)'
    )
    aml_explanation = models.TextField(
        null=True, blank=True, help_text='Wyjaśnienie zablokowanego przelewu w ramach AML'
    )

    class Meta:
        db_table = 'transfers'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.system_route} | {self.amount} PLN → {self.recipient_iban}"
