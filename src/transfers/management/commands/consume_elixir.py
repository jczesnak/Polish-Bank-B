import time
import requests
import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from transfers.models import Transfer
from accounts.models import Account

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Odpytuje API Elixira o statusy przelewów i aktualizuje bazę.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Uruchomiono polling statusów z Elixir API..."))
        
        while True:
            try:
                # Odpytaj o przelewy PROCESSED
                resp_processed = requests.get('http://host.docker.internal:8081/api/elixir/payments/processed', timeout=5)
                if resp_processed.status_code == 200:
                    for p in resp_processed.json():
                        self.process_status(p.get('paymentId'), 'COMPLETED')
                
                # Odpytaj o przelewy REJECTED
                resp_rejected = requests.get('http://host.docker.internal:8081/api/elixir/payments/rejected', timeout=5)
                if resp_rejected.status_code == 200:
                    for p in resp_rejected.json():
                        self.process_status(p.get('paymentId'), 'FAILED')

                # Odpytaj o przelewy BLOCKED (Traktujemy roboczo jako FAILED lub do zwrotu środków)
                resp_blocked = requests.get('http://host.docker.internal:8081/api/elixir/payments/blocked', timeout=5)
                if resp_blocked.status_code == 200:
                    for p in resp_blocked.json():
                        self.process_status(p.get('paymentId'), 'FAILED')

            except Exception as e:
                logger.error(f"Błąd podczas pollingu API Elixir: {e}")

            # Odczekaj 5 sekund przed kolejnym zapytaniem
            time.sleep(5)

    def process_status(self, payment_id, status):
        if not payment_id:
            return

        with transaction.atomic():
            try:
                # Szukamy tylko z system_route=ELIXIR żeby unikać konfliktów z innymi systemami
                transfer = Transfer.objects.select_for_update().get(id=payment_id, system_route='ELIXIR')
            except Transfer.DoesNotExist:
                return

            # Interesują nas tylko przelewy w statusie PENDING
            if transfer.status != 'PENDING':
                return

            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)

            if status == 'COMPLETED':
                if account.blocked_funds >= transfer.amount:
                    account.blocked_funds -= transfer.amount
                else:
                    account.blocked_funds = 0
                
                account.balance -= transfer.amount
                account.save()
                
                transfer.status = 'COMPLETED'
                transfer.save()
                logger.info(f"Przelew {payment_id} zakończony sukcesem (COMPLETED).")

            elif status == 'FAILED':
                # Zdejmujemy blokadę, środki wracają do pełnej dyspozycji
                if account.blocked_funds >= transfer.amount:
                    account.blocked_funds -= transfer.amount
                else:
                    account.blocked_funds = 0
                account.save()
                
                transfer.status = 'FAILED'
                transfer.save()
                logger.info(f"Przelew {payment_id} odrzucony/zablokowany w Elixir (FAILED).")
