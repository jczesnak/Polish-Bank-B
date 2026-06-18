import uuid
from django.db import models
from accounts.models import User, Account


class BlikCode(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Aktywny'
        USED = 'USED', 'Użyty'
        EXPIRED = 'EXPIRED', 'Wygasły'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blik_codes')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='blik_codes')
    code = models.CharField(max_length=6)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blik_codes'
        ordering = ['-created_at']

    def __str__(self):
        return f"BLIK {self.code} ({self.user.email}) [{self.status}]"


class BlikTransaction(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Oczekująca'
        AUTHORIZED = 'AUTHORIZED', 'Autoryzowana'
        COMPLETED = 'COMPLETED', 'Zakończona'
        REJECTED = 'REJECTED', 'Odrzucona'
        TIMEOUT = 'TIMEOUT', 'Timeout'

    class RejectReason(models.TextChoices):
        INSUFFICIENT_FUNDS = 'INSUFFICIENT_FUNDS', 'Brak środków'
        USER_DECLINED = 'USER_DECLINED', 'Odrzucono przez użytkownika'
        AML_BLOCK = 'AML_BLOCK', 'Blokada AML'
        OTHER = 'OTHER', 'Inny powód'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    klik_transaction_id = models.UUIDField(unique=True)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='blik_transactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='blik_transactions')
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='PLN')
    merchant_name = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    reject_reason = models.CharField(max_length=30, choices=RejectReason.choices, blank=True)
    needs_parent_auth = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'blik_transactions'
        ordering = ['-created_at']

    def __str__(self):
        return f"BLIK TX {self.klik_transaction_id} {self.amount} PLN [{self.status}]"


class PhoneAlias(models.Model):
    """Alias P2P (przelew na telefon) zarejestrowany przez ten bank w KLIK.

    Lokalny rejestr aliasów należących do klientów tego banku. KLIK trzyma
    globalny rejestr telefon → bank/IBAN, ale nie udostępnia listy per bank,
    więc cache'ujemy własne aliasy tutaj (m.in. po to, by klient mógł je
    wyrejestrować).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='phone_aliases')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='phone_aliases')
    phone = models.CharField(max_length=16, unique=True)
    klik_alias_id = models.UUIDField(null=True, blank=True)
    zone = models.CharField(max_length=2, default='PL')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blik_phone_aliases'
        ordering = ['-created_at']

    def __str__(self):
        return f"P2P {self.phone} → {self.account.iban} ({self.user.email})"


class P2pContact(models.Model):
    """Zapisany kontakt P2P (przelew na telefon) klienta tego banku.

    Pozwala wysłać przelew na telefon do zapisanej osoby bez ponownego
    wpisywania numeru. Kontakt jest prywatny dla właściciela (user).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='p2p_contacts')
    name = models.CharField(max_length=120)
    phone = models.CharField(max_length=16)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'blik_p2p_contacts'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['user', 'phone'], name='uniq_p2p_contact_user_phone'),
        ]

    def __str__(self):
        return f"{self.name} ({self.phone}) — {self.user.email}"
