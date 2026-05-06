from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from transfers.models import Transfer
from accounts.models import Account


class Command(BaseCommand):
    help = 'Księguje oczekujące przelewy wewnętrzne, których scheduled_at minął.'

    def handle(self, *args, **options):
        now = timezone.now()
        pending = Transfer.objects.filter(
            status=Transfer.Status.PENDING,
            system_route=Transfer.TransferSystem.INTERNAL,
            scheduled_at__lte=now,
        ).select_related('sender_account')

        processed = 0
        failed = 0

        for transfer in pending:
            with transaction.atomic():
                try:
                    sender = Account.objects.select_for_update().get(id=transfer.sender_account.id)
                    receiver = Account.objects.select_for_update().get(iban=transfer.recipient_iban)

                    sender.balance -= transfer.amount
                    sender.blocked_funds -= transfer.amount
                    receiver.balance += transfer.amount
                    sender.save()
                    receiver.save()

                    transfer.status = Transfer.Status.COMPLETED
                    transfer.processed_at = now
                    transfer.save()
                    processed += 1
                except Account.DoesNotExist:
                    try:
                        sender = Account.objects.select_for_update().get(id=transfer.sender_account.id)
                        sender.blocked_funds -= transfer.amount
                        sender.save()
                    except Account.DoesNotExist:
                        pass
                    transfer.status = Transfer.Status.FAILED
                    transfer.processed_at = now
                    transfer.save()
                    failed += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Przetworzono {processed} przelew(ów), {failed} nieudanych.'
            )
        )
