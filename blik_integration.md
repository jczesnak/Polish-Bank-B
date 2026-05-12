# Integracja z systemem KLIK (BLIK)

## 1. Opis

Polish Bank B integruje się z zewnętrznym systemem KLIK obsługującym płatności BLIK (C2B — Customer to Business). KLIK pełni rolę routera płatności — nie przechowuje środków, zarządza logiką autoryzacji kodów i rozliczeniami między bankami.

Repo systemu KLIK: https://github.com/MarshallBjorn/KLIK-payments

---

## 2. Przepływ płatności

```
Klient                  Polish Bank B           KLIK                    Merchant
  |                          |                    |                         |
  |-- POST /blik/generate/ ->|                    |                         |
  |                          |-- POST /codes/generate -->                   |
  |                          |<-- { code: "123456" } --                     |
  |<-- { code: "123456" } ---|                    |                         |
  |                          |                    |                         |
  | (klient wpisuje kod u merchanta)              |                         |
  |                          |                    |<-- POST /payments/initiate --
  |                          |<-- POST /webhook/authorize --                |
  |                          |-- (sprawdź środki, zablokuj kwotę)          |
  |                          |-- POST /payments/confirm (ACCEPTED) -->      |
  |                          |                    |-- COMPLETED ----------->|
```

---

## 3. Zaimplementowane endpointy

### Po stronie Polish Bank B

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `POST` | `/api/blik/generate/` | Generuje 6-cyfrowy kod BLIK dla klienta |
| `POST` | `/api/blik/webhook/authorize/` | Webhook od KLIK — bank autoryzuje płatność |
| `POST` | `/api/blik/webhook/ping/` | Healthcheck od KLIK przy rejestracji webhooka |
| `GET`  | `/api/blik/transactions/` | Historia transakcji BLIK zalogowanego klienta |

### Wywoływane u KLIK

| Metoda | Ścieżka | Opis |
|--------|---------|------|
| `POST` | `/api/v1/codes/generate` | Generuje kod w systemie KLIK |
| `POST` | `/api/v1/payments/confirm` | Potwierdza lub odrzuca płatność |
| `GET`  | `/api/v1/payments/status/{id}` | Sprawdza status transakcji |

---

## 4. Nowe pliki w projekcie

```
src/blik/
├── models.py         — modele BlikCode i BlikTransaction
├── services.py       — KlikService (HTTP do systemu KLIK)
├── serializers.py    — walidacja danych wejściowych
├── views.py          — logika endpointów
├── urls.py           — routing
├── admin.py          — panel admina
└── migrations/
    └── 0001_initial.py
```

---

## 5. Konfiguracja środowiska

W pliku `.env` muszą być ustawione:

```
INTEGRATIONS_BLIK_URL=http://host.docker.internal:8000
BLIK_API_KEY=klik_<klucz_od_operatora_KLIK>
```

> `host.docker.internal` zamiast `localhost` — backend działa w Dockerze i musi dotrzeć do KLIK na hoście.

---

## 6. Porty — oba systemy równocześnie

Aby uniknąć konfliktu portów, backend Polish Bank B został przestawiony na port `8080`. KLIK działa na swoim domyślnym porcie `8000` — **bez żadnych zmian w ich repozytorium**.

| Serwis | Adres |
|--------|-------|
| Polish Bank B — frontend | `http://localhost:4200` |
| Polish Bank B — backend / Swagger | `http://localhost:8080` |
| Polish Bank B — admin | `http://localhost:8080/admin/` |
| KLIK — backend | `http://localhost:8000` |
| KLIK — admin | `http://localhost:8000/admin/` |

---

## 7. Onboarding — rejestracja banku w systemie KLIK

Mając dostęp do ich repo, możesz zarejestrować bank samodzielnie:

**1. Uruchom KLIK:**
```
cd C:\KLIK-payments
docker compose -f docker-compose.yml -f docker-compose-dev.yml up --build
```

**2. Utwórz superusera:**
```
docker compose -f docker-compose.yml -f docker-compose-dev.yml exec web python manage.py createsuperuser
```

**3. Wejdź na `http://localhost:8000/admin/`** i dodaj nowy bank:

- **Name:** Polish Bank B
- **Zone:** PL
- **Webhook url:** `http://host.docker.internal:8080/api/blik/webhook/authorize/`
- **C2b enabled:** True
- **Active:** True

Po zapisaniu Django Admin pokazuje `api_key` **tylko raz** — skopiuj go i wstaw do `.env` jako `BLIK_API_KEY`.

---

## 8. Uruchomienie Polish Bank B

```
cd C:\Polish-Bank-B
docker compose up --build
```

---

## 9. Testowanie w Postmanie

### Krok 1 — Rejestracja
```
POST http://localhost:8080/api/auth/register/
```
```json
{
  "first_name": "Jan",
  "last_name": "Kowalski",
  "email": "jan@test.com",
  "pesel": "12345678901",
  "phone_number": "123456789",
  "password": "haslo1234",
  "password_confirm": "haslo1234"
}
```
Skopiuj `access` token i `id` usera z odpowiedzi.

### Krok 2 — Pobierz konto
```
GET http://localhost:8080/api/accounts/
Authorization: Bearer <access_token>
```
Skopiuj `id` konta.

### Krok 3 — Wygeneruj kod BLIK
```
POST http://localhost:8080/api/blik/generate/
Authorization: Bearer <access_token>
```
```json
{ "account_id": "<id_konta>" }
```
Odpowiedź: `{ "code": "123456", "expires_in": 120, "expires_at": "..." }`

### Krok 4 — Zasymuluj webhook od KLIK
```
POST http://localhost:8080/api/blik/webhook/authorize/
(bez tokena)
```
```json
{
  "transaction_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": "<id_usera>",
  "amount": "50.00",
  "currency": "PLN",
  "merchant_name": "Sklep testowy"
}
```
Odpowiedź: `{ "received": true, "will_prompt_user": true }`

### Krok 5 — Sprawdź historię transakcji
```
GET http://localhost:8080/api/blik/transactions/
Authorization: Bearer <access_token>
```
Transakcja powinna mieć status `AUTHORIZED`.

---

## 10. Możliwe błędy

| Błąd | Przyczyna | Rozwiązanie |
|------|-----------|-------------|
| `502 Bad Gateway` | KLIK nie działa lub zły URL | Sprawdź czy KLIK jest uruchomiony, sprawdź `INTEGRATIONS_BLIK_URL` |
| `401 Unauthorized` | Zły `BLIK_API_KEY` | Sprawdź klucz w `.env`, zrestartuj kontener |
| `404` na webhook | Brak aktywnego kodu BLIK | Najpierw wywołaj `/blik/generate/`, potem webhook |
| `Connection refused` | `localhost` zamiast `host.docker.internal` | Popraw URL w `.env` |
