from django.db import transaction
from django.utils import timezone

from accounts.models import Account
from .models import BlikTransaction
from .services import KlikError, KlikService


class BlikPaymentError(Exception):
    def __init__(self, message: str, http_status: int = 400):
        self.message = message
        self.http_status = http_status
        super().__init__(message)


def accept_blik_transaction(blik_tx: BlikTransaction) -> BlikTransaction:
    if blik_tx.status != BlikTransaction.Status.PENDING:
        raise BlikPaymentError('Transakcja nie oczekuje na autoryzację.', 400)

    amount = blik_tx.amount
    try:
        KlikService().confirm_payment(
            transaction_id=str(blik_tx.klik_transaction_id),
            decision='ACCEPTED',
        )
    except KlikError as exc:
        with transaction.atomic():
            account = Account.objects.select_for_update().get(pk=blik_tx.account_id)
            account.blocked_funds -= amount
            account.save(update_fields=['blocked_funds'])
            blik_tx.status = BlikTransaction.Status.REJECTED
            blik_tx.reject_reason = BlikTransaction.RejectReason.OTHER
            blik_tx.completed_at = timezone.now()
            blik_tx.save(update_fields=['status', 'reject_reason', 'completed_at'])
        raise BlikPaymentError(f'Błąd potwierdzenia w KLIK: {exc.message}', 502) from exc

    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=blik_tx.account_id)
        account.blocked_funds -= amount
        account.balance -= amount
        account.save(update_fields=['blocked_funds', 'balance'])
        blik_tx.status = BlikTransaction.Status.COMPLETED
        blik_tx.completed_at = timezone.now()
        blik_tx.save(update_fields=['status', 'completed_at'])
    return blik_tx


def reject_blik_transaction(
    blik_tx: BlikTransaction,
    reason: str = 'USER_DECLINED',
) -> BlikTransaction:
    if blik_tx.status != BlikTransaction.Status.PENDING:
        raise BlikPaymentError('Transakcja nie oczekuje na autoryzację.', 400)

    amount = blik_tx.amount
    reject_reason = BlikTransaction.RejectReason.USER_DECLINED
    if reason == 'INSUFFICIENT_FUNDS':
        reject_reason = BlikTransaction.RejectReason.INSUFFICIENT_FUNDS

    try:
        KlikService().confirm_payment(
            transaction_id=str(blik_tx.klik_transaction_id),
            decision='REJECTED',
            reject_reason=reason,
        )
    except KlikError:
        pass

    with transaction.atomic():
        account = Account.objects.select_for_update().get(pk=blik_tx.account_id)
        account.blocked_funds -= amount
        account.save(update_fields=['blocked_funds'])
        blik_tx.status = BlikTransaction.Status.REJECTED
        blik_tx.reject_reason = reject_reason
        blik_tx.completed_at = timezone.now()
        blik_tx.save(update_fields=['status', 'reject_reason', 'completed_at'])
    return blik_tx
