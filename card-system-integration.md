# Integracja Systemu Kart Płatniczych (Card Network) z Polish Bank B

Ten przewodnik krok po kroku wyjaśnia, jak poprawnie uruchomić, skonfigurować i przetestować system kart płatniczych (repozytorium `Karty-Platnicze-Aplikacje-Biznesowe`) wraz z Twoją aplikacją bankową `Polish-Bank-B`.

## 1. Konfiguracja po stronie Banku (`Polish-Bank-B`)

Aby Twój bank mógł wysyłać zapytania o wydanie nowej karty, autoryzacje itp., musisz skonfigurować w nim adresy i klucze dostępowe do centrali kart.

Otwórz plik `.env` w głównym katalogu `Polish-Bank-B` (lub skopiuj z `.env.example`) i upewnij się, że posiadasz następujące zmienne:

```env
# URL, pod którym bank widzi procesor kart (Gateway). 
# Jeśli korzystasz z Docker Bridge (tej samej sieci), zostaw nazwe kontenera. 
# Jeśli odpalasz z hosta, użyj http://localhost:8072
INTEGRATIONS_CARDS_URL=http://cards_gateway_app:8000

# Klucze dostępowe banku (takie same muszą być w bazie serwisu kart)
CARDS_API_KEY=bank-key-pl-b
CARDS_API_SECRET=secret-pl-b-hmac
```

## 2. Konfiguracja po stronie Systemu Kart (`Karty-Platnicze-Aplikacje-Biznesowe`)

System kart płatniczych w celu rozliczania transakcji wysyła powiadomienia (tzw. Clearing / Settlement) z powrotem do banku (webhooki). 

W repozytorium kart otwórz plik `docker-compose.yaml` i zlokalizuj serwis `card-provider`. Upewnij się, że adres URL kieruje do kontenera z backendem Twojego banku:

```yaml
# Fragment z docker-compose.yaml -> service: card-provider -> environment
BANK_CAPTURE_URL_POLISH_BANK_B: "http://polish-bank-b-backend-1:8000/api/cards"
```

## 3. Uruchamianie Systemów

### Krok A: Uruchomienie Systemu Kart Płatniczych
Przejdź do katalogu z aplikacjami kart (np. przez terminal) i uruchom środowisko:
```bash
cd "c:\Users\Kuba\Documents\Aplikacje Biznesowe\Karty-Platnicze-Aplikacje-Biznesowe"
docker-compose up -d --build
```
Spowoduje to uruchomienie: bazy Postgres, Minio, Card Providera, Payment Gateway oraz Panelu Administratora.

### Krok B: Uruchomienie Polish Bank B
Przejdź do katalogu ze swoim bankiem i uruchom go podobnie (pamiętając, że jego backend i frontend muszą działać, a backend mieć dostęp do sieci kart).
```bash
cd "c:\Users\Kuba\Documents\Aplikacje Biznesowe\Polish-Bank-B"
docker-compose up -d
```

## 4. Dodanie Banku do Sieci Kart (Admin Panel)

Aby bank `Polish-Bank-B` mógł działać, musi być autoryzowany po stronie dostawcy kart. Wejdź w panel administratora systemu kart (domyślnie pod adresem **`http://localhost:3072`**).

Musisz tam:
1. **Dodać nowy Bank**: Jako API_KEY i HMAC_SECRET podaj dokładnie to samo, co wpisałeś w pliku `.env` banku (odpowiednio `bank-key-pl-b` i `secret-pl-b-hmac`).
2. **Przypisać walutę i Prefix (BIN)**: Ustaw walutę na PLN oraz podaj początek numerów kart dla swojego banku (np. `411111` lub cokolwiek ustaliliście).

## 5. Jak Testować Działanie?

1. **Wydawanie kart:** Zaloguj się na frontendzie Polish Bank B (`http://localhost:4200` lub odpowiednim porcie) wejdź w zakładkę kart, a następnie kliknij w **Zamów nową kartę** np. `PREPAID`. 
2. **Płatność kartą (POS Emulator):** Wejdź pod adres **`http://localhost:8072/pos`**. Zobaczysz formularz terminala POS. 
3. **Autoryzacja:** Przeklej z pulpitu swojego banku numer testowej karty i datę ważności, i wciśnij "Authorize Payment". Terminal wyśle sygnał ISO 8583 do Gateway'a, ten odbije to do Card Providera, a ten przeliczy pieniądze i odeśle informację `APPROVED`.

> [!WARNING]
> Pamiętaj, o niedawno zgłoszonym błędzie. Dla kart typu **Virtual / Physical**, aby transakcja nie zwróciła błędu `51 Insufficient Funds`, Card Provider musi zostać naprawiony tak, by pukał po saldo do webhooka w Twoim banku! Karty PREPAID powinny śmigać bez problemu. Dodatkowo w POS Simulator testuj używając 2-cyfrowego formatu roku (np. `25` zamiast `2025`).
