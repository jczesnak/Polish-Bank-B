"""Seeder danych demonstracyjnych dla Polish-Bank-B.

Tworzy deterministyczny zestaw kont (superuser, rodzic, junior, zwykli
klienci) wraz z rachunkami, kartami płatniczymi, PIN-em BLIK oraz kilkoma
kontaktami P2P. Dane są stałe, więc lista loginów/haseł jest powtarzalna.

Użycie:
    python manage.py seed              # dodaje/aktualizuje dane (idempotentnie)
    python manage.py seed --flush      # najpierw czyści dane demo, potem seeduje

UWAGA: dane wyłącznie do środowiska deweloperskiego/testowego.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import hashers
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, JuniorProfile
from blik.models import P2pContact, PhoneAlias
from cards.models import PaymentCard
from transfers.models import Transfer

User = None  # ustawiane w handle(), żeby uniknąć importu na poziomie modułu


# --- Dane demonstracyjne (stałe, deterministyczne) ----------------------------

BLIK_PIN = "1234"

USERS = [
    {
        "key": "admin",
        "email": "admin@bank-b.pl",
        "password": "Admin123!",
        "first_name": "Admin",
        "last_name": "Systemowy",
        "pesel": "80010100000",
        "phone": "500000000",
        "is_staff": True,
        "is_superuser": True,
        "accounts": [
            {"iban": "PL98102010269999000000000001", "type": "CHECKING",
             "balance": "10000.00", "card": "4012003333300000"},
        ],
    },
    {
        "key": "jan",
        "email": "jan.kowalski@example.com",
        "password": "Test1234!",
        "first_name": "Jan",
        "last_name": "Kowalski",
        "pesel": "85010112345",
        "phone": "512345678",
        "accounts": [
            {"iban": "PL95102010261111000000000001", "type": "CHECKING",
             "balance": "15250.75", "card": "4012001111000002"},
            {"iban": "PL68102010261111000000000002", "type": "SAVINGS",
             "balance": "48000.00", "card": None},
        ],
    },
    {
        "key": "anna",
        "email": "anna.nowak@example.com",
        "password": "Test1234!",
        "first_name": "Anna",
        "last_name": "Nowak",
        "pesel": "90050554321",
        "phone": "600100200",
        "accounts": [
            {"iban": "PL59102010262222000000000001", "type": "CHECKING",
             "balance": "8420.50", "card": "5105002222000001"},
        ],
    },
    {
        "key": "piotr",
        "email": "piotr.wisniewski@example.com",
        "password": "Test1234!",
        "first_name": "Piotr",
        "last_name": "Wiśniewski",
        "pesel": "78112399887",
        "phone": "698112233",
        "accounts": [
            {"iban": "PL23102010263333000000000001", "type": "CHECKING",
             "balance": "1990.00", "card": "4012003333000000"},
        ],
    },
    {
        "key": "kuba",
        "email": "kuba.kowalski@example.com",
        "password": "Junior123!",
        "first_name": "Kuba",
        "last_name": "Kowalski",
        "pesel": "15030712345",
        "phone": "533444555",
        "junior_parent": "jan",  # konto dziecka powiązane z rodzicem (jan)
        "accounts": [
            {"iban": "PL84102010264444000000000001", "type": "JUNIOR",
             "balance": "120.00", "card": "5105004444000009",
             "parent_iban": "PL95102010261111000000000001"},
        ],
    },
    {
        "key": "maria",
        "email": "maria.lewandowska@example.com",
        "password": "Test1234!",
        "first_name": "Maria",
        "last_name": "Lewandowska",
        "pesel": "82070554321",
        "phone": "606707808",
        "accounts": [
            {"iban": "PL48102010265555000000000001", "type": "CHECKING",
             "balance": "27600.00", "card": "4012005555000006"},
        ],
    },
    {
        "key": "zosia",
        "email": "zosia.lewandowska@example.com",
        "password": "Junior123!",
        "first_name": "Zosia",
        "last_name": "Lewandowska",
        "pesel": "12041012345",
        "phone": "511222333",
        "junior_parent": "maria",
        "accounts": [
            {"iban": "PL21102010265555000000000002", "type": "JUNIOR",
             "balance": "250.00", "card": "5105005555100009",
             "parent_iban": "PL48102010265555000000000001"},
        ],
    },
    {
        "key": "antek",
        "email": "antek.lewandowski@example.com",
        "password": "Junior123!",
        "first_name": "Antek",
        "last_name": "Lewandowski",
        "pesel": "14081012345",
        "phone": "522333444",
        "junior_parent": "maria",
        "accounts": [
            {"iban": "PL91102010265555000000000003", "type": "JUNIOR",
             "balance": "75.50", "card": "4012005555200002",
             "parent_iban": "PL48102010265555000000000001"},
        ],
    },
    {
        "key": "ola",
        "email": "ola.lewandowska@example.com",
        "password": "Junior123!",
        "first_name": "Ola",
        "last_name": "Lewandowska",
        "pesel": "17021512345",
        "phone": "533444556",
        "junior_parent": "maria",
        "accounts": [
            {"iban": "PL64102010265555000000000004", "type": "JUNIOR",
             "balance": "300.00", "card": None,
             "parent_iban": "PL48102010265555000000000001"},
        ],
    },
]


# Liczba operacji (przelewów wychodzących) tworzonych dla każdego użytkownika.
TRANSFERS_PER_USER = 20

# Pula odbiorców przelewów: (nazwa, IBAN, [tytuły], system_route).
TRANSFER_TARGETS = [
    ("Biedronka Jeronimo Martins", "PL27114020040000300201355387",
     ["Zakupy spożywcze", "Zakupy"], "ELIXIR"),
    ("Allegro sp. z o.o.", "PL61109010140000071219812874",
     ["Zamówienie Allegro", "Zakup online"], "EXPRESS_ELIXIR"),
    ("PGE Obrót S.A.", "PL83101010230000261395100000",
     ["Rachunek za prąd", "Energia elektryczna"], "ELIXIR"),
    ("Orange Polska S.A.", "PL49102010260000110200000000",
     ["Abonament telefoniczny", "Faktura Orange"], "ELIXIR"),
    ("Netflix International B.V.", "PL15105014451000009223558899",
     ["Subskrypcja Netflix"], "ELIXIR"),
    ("Spółdzielnia Mieszkaniowa", "PL92124010370000821000000000",
     ["Czynsz", "Opłata za mieszkanie"], "ELIXIR"),
    ("Urząd Skarbowy", "PL10101010230000261395100000",
     ["Zaliczka PIT", "Podatek"], "SORBNET"),
    ("ZUS", "PL83101010230000261395100001",
     ["Składka ZUS"], "SORBNET"),
    ("Jan Testowy", "PL45109024020000000610000001",
     ["Zwrot pożyczki", "Za obiad", "Prezent"], "INTERNAL"),
    ("Apple Distribution Intl", "PL77116022020000000277788990",
     ["App Store", "iCloud"], "EXPRESS_ELIXIR"),
]


def masked(pan: str) -> str:
    return f"{pan[:6]}******{pan[-4:]}"


class Command(BaseCommand):
    help = "Seeduje deterministyczne dane demonstracyjne (konta, karty, BLIK, P2P)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Usuwa istniejące dane demo (po e-mailach) przed seedowaniem.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        global User
        from accounts.models import User as UserModel
        User = UserModel

        emails = [u["email"] for u in USERS]

        if options["flush"]:
            # Transfer.sender_account ma on_delete=PROTECT, więc przelewy trzeba
            # skasować przed użytkownikami/rachunkami.
            Transfer.objects.filter(sender_account__user__email__in=emails).delete()
            deleted, _ = User.objects.filter(email__in=emails).delete()
            self.stdout.write(self.style.WARNING(f"Usunięto dane demo ({deleted} obiektów)."))

        users_by_key = {}
        hashed_pin = hashers.make_password(BLIK_PIN)

        # 1) Użytkownicy + rachunki + karty
        for spec in USERS:
            user, created = User.objects.update_or_create(
                email=spec["email"],
                defaults={
                    "username": spec["email"],
                    "first_name": spec["first_name"],
                    "last_name": spec["last_name"],
                    "pesel": spec["pesel"],
                    "phone_number": spec["phone"],
                    "blik_pin": hashed_pin,
                    "is_staff": spec.get("is_staff", False),
                    "is_superuser": spec.get("is_superuser", False),
                    "is_active": True,
                },
            )
            user.set_password(spec["password"])
            user.save()
            users_by_key[spec["key"]] = user

            for acc in spec["accounts"]:
                account, _ = Account.objects.update_or_create(
                    iban=acc["iban"],
                    defaults={
                        "user": user,
                        "balance": Decimal(acc["balance"]),
                        "account_type": acc["type"],
                    },
                )
                if acc.get("card"):
                    pan = acc["card"]
                    PaymentCard.objects.update_or_create(
                        card_number=pan,
                        defaults={
                            "account": account,
                            "external_card_id": f"seed-{pan}",
                            "masked_number": masked(pan),
                            "is_active": True,
                        },
                    )

            tag = "utworzono" if created else "zaktualizowano"
            self.stdout.write(f"  użytkownik {tag}: {spec['email']}")

        # 2) Powiązania junior <-> rodzic (parent_account + profil)
        for spec in USERS:
            parent_key = spec.get("junior_parent")
            if not parent_key:
                continue
            child = users_by_key[spec["key"]]
            parent = users_by_key[parent_key]

            for acc in spec["accounts"]:
                if acc.get("parent_iban"):
                    junior_acc = Account.objects.get(iban=acc["iban"])
                    junior_acc.parent_account = Account.objects.get(iban=acc["parent_iban"])
                    junior_acc.save(update_fields=["parent_account"])

            JuniorProfile.objects.update_or_create(
                user=child,
                defaults={
                    "parent": parent,
                    "daily_limit": Decimal("100.00"),
                    "blik_limit": Decimal("50.00"),
                },
            )
            self.stdout.write(f"  profil junior: {child.email} (rodzic: {parent.email})")

        # 3) Przykładowe kontakty P2P (przelew na telefon)
        jan = users_by_key["jan"]
        contacts = [
            ("Anna Nowak", "600100200"),
            ("Piotr Wiśniewski", "698112233"),
        ]
        for name, phone in contacts:
            P2pContact.objects.update_or_create(
                user=jan, phone=phone, defaults={"name": name}
            )

        # 4) Alias telefonu P2P dla Anny (jej konto główne)
        anna = users_by_key["anna"]
        anna_acc = Account.objects.get(iban="PL59102010262222000000000001")
        PhoneAlias.objects.update_or_create(
            phone=anna.phone_number,
            defaults={"user": anna, "account": anna_acc, "zone": "PL"},
        )

        # 5) Operacje (przelewy wychodzące) - po TRANSFERS_PER_USER na użytkownika
        self._seed_transfers(users_by_key)

        self.stdout.write(self.style.SUCCESS("\nSeedowanie zakończone."))
        self._print_summary()

    def _seed_transfers(self, users_by_key):
        """Tworzy stałą liczbę przelewów wychodzących dla każdego użytkownika.

        Dane są deterministyczne (stały seed). Operacje nie modyfikują sald -
        służą jako historia demonstracyjna. Idempotentne: istniejące przelewy
        seedowanych użytkowników są usuwane przed ponownym utworzeniem.
        """
        rng = random.Random(2026)
        emails = [u["email"] for u in USERS]

        Transfer.objects.filter(sender_account__user__email__in=emails).delete()

        statuses = (
            [Transfer.Status.COMPLETED] * 16
            + [Transfer.Status.PROCESSING] * 2
            + [Transfer.Status.PENDING, Transfer.Status.FAILED]
        )
        now = timezone.now()
        total = 0

        for user in users_by_key.values():
            account = (
                user.accounts.filter(account_type=Account.AccountType.CHECKING).first()
                or user.accounts.first()
            )
            if account is None:
                continue

            transfers = []
            for i in range(TRANSFERS_PER_USER):
                name, iban, titles, route = rng.choice(TRANSFER_TARGETS)
                status = rng.choice(statuses)
                amount = Decimal(rng.randrange(1500, 75000)) / 100  # 15.00 - 749.99
                created = now - timedelta(
                    days=rng.randint(0, 120), minutes=rng.randint(0, 1439)
                )
                processed = (
                    created + timedelta(minutes=rng.randint(1, 240))
                    if status == Transfer.Status.COMPLETED
                    else None
                )
                transfers.append(Transfer(
                    sender_account=account,
                    recipient_iban=iban,
                    recipient_name=name,
                    amount=amount,
                    title=rng.choice(titles),
                    system_route=route,
                    status=status,
                    processed_at=processed,
                ))

            created_objs = Transfer.objects.bulk_create(transfers)
            # created_at ma auto_now_add=True (ustawia "teraz") - nadpisujemy je,
            # żeby historia operacji była rozłożona w czasie.
            for obj in created_objs:
                obj.created_at = now - timedelta(
                    days=rng.randint(0, 120), minutes=rng.randint(0, 1439)
                )
            Transfer.objects.bulk_update(created_objs, ["created_at"])
            total += len(created_objs)

        self.stdout.write(f"  utworzono operacji (przelewów): {total}")

    def _print_summary(self):
        line = "-" * 96
        self.stdout.write("\nDANE DOSTĘPOWE (środowisko testowe):")
        self.stdout.write(line)
        header = f"{'E-MAIL':32} {'HASŁO':12} {'TELEFON':10} {'PIN BLIK':8} ROLA"
        self.stdout.write(header)
        self.stdout.write(line)
        for spec in USERS:
            if spec.get("is_superuser"):
                rola = "admin/superuser"
            elif spec.get("junior_parent"):
                rola = f"junior (rodzic: {spec['junior_parent']})"
            else:
                rola = "klient"
            self.stdout.write(
                f"{spec['email']:32} {spec['password']:12} {spec['phone']:10} {BLIK_PIN:8} {rola}"
            )
        self.stdout.write(line)
        self.stdout.write("\nRACHUNKI I KARTY:")
        self.stdout.write(line)
        for spec in USERS:
            for acc in spec["accounts"]:
                card = acc.get("card") or "-"
                self.stdout.write(
                    f"{spec['email']:32} {acc['iban']:28} {acc['type']:9} "
                    f"saldo={acc['balance']:>10} karta={card}"
                )
        self.stdout.write(line)
