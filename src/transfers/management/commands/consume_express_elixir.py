import time
import requests
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from transfers.models import Transfer
from accounts.models import Account

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Odpytuje API Express Elixira o statusy szybkich przelewów i aktualizuje bazę.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Uruchomiono polling statusów z Express Elixir API..."))
        
        while True:
            try:
                # Odpytaj o przelewy PROCESSED
                resp_processed = requests.get('http://host.docker.internal:8082/api/express/payments/status/PROCESSED', timeout=5)
                if resp_processed.status_code == 200:
                    for p in resp_processed.json():
                        self.process_status(p.get('paymentId'), 'COMPLETED')
                
                # Odpytaj o przelewy REJECTED
                resp_rejected = requests.get('http://host.docker.internal:8082/api/express/payments/status/REJECTED', timeout=5)
                if resp_rejected.status_code == 200:
                    for p in resp_rejected.json():
                        self.process_status(p.get('paymentId'), 'FAILED')

                # Odpytaj o przelewy BLOCKED
                resp_blocked = requests.get('http://host.docker.internal:8082/api/express/payments/status/BLOCKED', timeout=5)
                if resp_blocked.status_code == 200:
                    for p in resp_blocked.json():
                        self.process_status(p.get('paymentId'), 'FAILED')

            except Exception as e:
                logger.error(f"Błąd podczas pollingu API Express Elixir: {e}")

            # Express Elixir to system natychmiastowy, możemy pytać częściej np. co 2 sekundy
            time.sleep(2)

    def process_status(self, payment_id, status):
        if not payment_id:
            return

        with transaction.atomic():
            try:
                # Szukamy tylko z system_route=EXPRESS_ELIXIR żeby unikać pomyłek (choć UUID powinno być unikalne)
                transfer = Transfer.objects.select_for_update().get(id=payment_id, system_route='EXPRESS_ELIXIR')
            except Transfer.DoesNotExist:
                return

            if transfer.status == 'PENDING':
                account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
                
                if status == 'COMPLETED':
                    # Przelew przeszedł, odejmujemy z balance i ściągamy blokadę z blocked_funds
                    if account.blocked_funds >= transfer.amount:
                        account.blocked_funds -= transfer.amount
                    account.balance -= transfer.amount
                    account.save()
                    transfer.status = 'COMPLETED'
                    transfer.save()
                    logger.info(f"Przelew Express {payment_id} zakończony sukcesem.")
                    
                elif status == 'FAILED':
                    # Przelew odrzucony/zablokowany, zdejmujemy tylko blokadę
                    if account.blocked_funds >= transfer.amount:
                        account.blocked_funds -= transfer.amount
                    account.save()
                    transfer.status = 'FAILED'
                    transfer.save()
                    logger.info(f"Przelew Express {payment_id} odrzucony.")
