import uuid
from django.db import models
from accounts.models import Account, User


class Transfer(models.Model):
    class TransferSystem(models.TextChoices):
        INTERNAL = 'INTERNAL', 'Wewnętrzny'
        ELIXIR = 'ELIXIR', 'Elixir'
        EXPRESS_ELIXIR = 'EXPRESS_ELIXIR', 'Express Elixir'
        KLIK = 'KLIK', 'KLIK'
        SORBNET = 'SORBNET', 'Sorbnet'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekujący'
        PENDING_APPROVAL = 'PENDING_APPROVAL', 'Oczekuje na zgodę rodzica'
        PROCESSING = 'PROCESSING', 'W realizacji'
        COMPLETED = 'COMPLETED', 'Zrealizowany'
        REJECTED = 'REJECTED', 'Odrzucony'
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


class ApprovalRequest(models.Model):
    class RequestType(models.TextChoices):
        TRANSFER = 'TRANSFER', 'Przelew'
        CARD_PAYMENT = 'CARD_PAYMENT', 'Płatność kartą'
        BLIK_PAYMENT = 'BLIK_PAYMENT', 'Płatność BLIK'

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekuje'
        APPROVED = 'APPROVED', 'Zatwierdzony'
        REJECTED = 'REJECTED', 'Odrzucony'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_type = models.CharField(max_length=20, choices=RequestType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    junior = models.ForeignKey(User, on_delete=models.CASCADE, related_name='junior_approval_requests')
    parent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parent_approval_requests')
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name='approval_requests')
    transfer = models.OneToOneField(
        Transfer, on_delete=models.CASCADE, null=True, blank=True, related_name='approval_request'
    )
    card_transaction = models.OneToOneField(
        'cards.CardTransaction',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_request',
    )
    blik_transaction = models.OneToOneField(
        'blik.BlikTransaction',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='approval_request',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'approval_requests'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.request_type} {self.status} ({self.junior.email})'
