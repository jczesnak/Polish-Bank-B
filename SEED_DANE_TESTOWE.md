# Dane testowe (seeder)

Dane generowane przez seeder: `accounts/management/commands/seed.py`.
Są **deterministyczne** - po każdym uruchomieniu wychodzą te same loginy, hasła i numery kont.

> ⚠️ Wyłącznie środowisko deweloperskie/testowe. Nie używać na produkcji.

## Uruchomienie

```bash
# w katalogu Polish-Bank-B
docker compose exec backend python manage.py seed          # idempotentnie (dodaje/aktualizuje)
docker compose exec backend python manage.py seed --flush  # czyści dane demo i seeduje od nowa
```

PIN BLIK dla wszystkich kont: **1234**

## Konta dostępowe

| E-mail | Hasło | Telefon | PIN BLIK | Rola |
|---|---|---|---|---|
| admin@bank-b.pl | `Admin123!` | 500000000 | 1234 | admin / superuser |
| jan.kowalski@example.com | `Test1234!` | 512345678 | 1234 | klient (rodzic) |
| anna.nowak@example.com | `Test1234!` | 600100200 | 1234 | klient |
| piotr.wisniewski@example.com | `Test1234!` | 698112233 | 1234 | klient |
| kuba.kowalski@example.com | `Junior123!` | 533444555 | 1234 | junior (rodzic: Jan) |
| maria.lewandowska@example.com | `Test1234!` | 606707808 | 1234 | klient (rodzic - 3 juniorów) |
| zosia.lewandowska@example.com | `Junior123!` | 511222333 | 1234 | junior (rodzic: Maria) |
| antek.lewandowski@example.com | `Junior123!` | 522333444 | 1234 | junior (rodzic: Maria) |
| ola.lewandowska@example.com | `Junior123!` | 533444556 | 1234 | junior (rodzic: Maria) |

## Rachunki i karty

| Właściciel | IBAN | Typ | Saldo (PLN) | Numer karty |
|---|---|---|---|---|
| Admin | PL98 1020 1026 9999 0000 0000 0001 | osobiste | 10 000,00 | 4012 0033 3333 0000 |
| Jan Kowalski | PL95 1020 1026 1111 0000 0000 0001 | osobiste | 15 250,75 | 4012 0011 1100 0002 |
| Jan Kowalski | PL68 1020 1026 1111 0000 0000 0002 | oszczędnościowe | 48 000,00 | - |
| Anna Nowak | PL59 1020 1026 2222 0000 0000 0001 | osobiste | 8 420,50 | 5105 0022 2200 0001 |
| Piotr Wiśniewski | PL23 1020 1026 3333 0000 0000 0001 | osobiste | 1 990,00 | 4012 0033 3300 0000 |
| Kuba Kowalski | PL84 1020 1026 4444 0000 0000 0001 | junior | 120,00 | 5105 0044 4400 0009 |
| Maria Lewandowska | PL48 1020 1026 5555 0000 0000 0001 | osobiste | 27 600,00 | 4012 0055 5500 0006 |
| Zosia Lewandowska | PL21 1020 1026 5555 0000 0000 0002 | junior | 250,00 | 5105 0055 5510 0009 |
| Antek Lewandowski | PL91 1020 1026 5555 0000 0000 0003 | junior | 75,50 | 4012 0055 5520 0002 |
| Ola Lewandowska | PL64 1020 1026 5555 0000 0000 0004 | junior | 300,00 | - |

## Powiązania rodzic - junior

- **Jan Kowalski** - 1 dziecko:
  - Kuba (konto junior podpięte pod konto osobiste Jana)
- **Maria Lewandowska** - 3 dzieci (kilka kont junior pod jednym rodzicem):
  - Zosia (junior)
  - Antek (junior)
  - Ola (junior)

Każde konto junior ma ustawiony `parent_account` (konto osobiste rodzica) oraz `JuniorProfile`
(limit dzienny 100 PLN, limit BLIK 50 PLN).

## Operacje (historia przelewów)

Seeder tworzy **20 przelewów wychodzących na każdego użytkownika** (łącznie 180),
z rachunku osobistego (lub junior, jeśli nie ma osobistego). Dane są deterministyczne
(stały seed), z różnymi:

- odbiorcami (Biedronka, Allegro, PGE, Orange, Netflix, US, ZUS, Apple itp.),
- kwotami (15,00 - 749,99 PLN),
- tytułami,
- systemami rozliczeniowymi (ELIXIR, Express Elixir, Sorbnet, wewnętrzny),
- statusami (głównie `COMPLETED`, część `PROCESSING` / `PENDING` / `FAILED`),
- datami rozłożonymi na ostatnie ~120 dni.

Liczbę operacji ustawia stała `TRANSFERS_PER_USER` w seederze.

> Uwaga: operacje to historia demonstracyjna - **nie modyfikują sald** rachunków.

## Kontakty P2P / aliasy telefonu

- Jan Kowalski ma zapisane kontakty P2P: Anna Nowak (600100200), Piotr Wiśniewski (698112233).
- Numer Anny Nowak (600100200) zarejestrowany jako alias telefonu P2P na jej koncie osobistym.
