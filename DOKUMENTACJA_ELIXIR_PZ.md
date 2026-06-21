# Dokumentacja Integracji Systemu Elixir-PZ w Polish-Bank-B

Niniejszy plik opisuje **dokładnie**, w jaki sposób nasz projekt (Polish-Bank-B zrealizowany w Django) zintegrował się z trzema systemami rozliczeniowymi symulatora `Elixir-PZ`. Przekaż ten dokument koledze z zespołu – znajdzie w nim gotowe wzorce, które może łatwo przenieść do swojego projektu.

Wszystkie systemy zewnętrzne wywoływaliśmy lokalnie (ze względu na architekturę Docker) poprzez `host.docker.internal`.

---

## 1. Serwisy Integracyjne (Wysyłanie Danych)
Całą logikę wyjściową zgrupowaliśmy w jednym pliku w Django:
👉 **Plik:** `src/transfers/services.py`

Utworzyliśmy w nim trzy dedykowane klasy integrujące:

### A. Standardowy Elixir (`ElixirIntegrationService`)
- **Port integracji:** `8081` (`/api/elixir/payments`)
- **Format:** Czysty XML (ISO 20022 - `pacs.008`).
- **Podejście:** Zastosowaliśmy prosty string interpolation (f-stringi) w Pythonie, by dynamicznie podstawić kwotę, datę, nazwę i konta do z góry zdefiniowanego szablonu XML.
- **Specyfika:** Trzeba pamiętać o odpowiednich tagach dla Elixira:
  ```xml
  <SttlmMtd>CLRG</SttlmMtd>
  <ClrSys><Cd>ELIXIR</Cd></ClrSys>
  ```
- **Odpowiedź:** Po uderzeniu POST-em z poprawnymi nagłówkami (`Content-Type: application/xml`), symulator pod adresem 8081 po prostu połyka XML. Zwrócenie kodu `200` wystarczy, by oznaczyć przelew jako przyjęty do realizacji (status wewnętrzny `PENDING`).

### B. Express Elixir (`ExpressElixirIntegrationService`)
- **Port integracji:** `8082` (`/api/payments`)
- **Format:** Lżejszy JSON.
- **Podejście:** W przeciwieństwie do Elixira standardowego, tu budujemy zwykły słownik (JSON) z atrybutem `type: "ELIXIR_EXPRESS"`. W JSON przekazujemy również wewnętrzny `paymentId` (ID przelewu z naszej bazy danych), co pozwala nam później na śledzenie jego losów w pętli asynchronicznej (zobacz sekcję 2).

### C. Sorbnet (`SorbnetIntegrationService`)
- **Port integracji:** `8083` (`/api/sorbnet/payments`)
- **Format:** XML (ISO 20022).
- **Podejście:** Tworzymy podobny XML jak dla systemu Standard, zmieniając tylko ServiceCode na `SORBNET`.
- **Weryfikacja odpowiedzi:** Tutaj musieliśmy zaimportować bibliotekę `xml.etree.ElementTree`. Serwer pod portem 8083 odpowiada nam XML-em informującym od razu o finalnym statusie (np. ze względu na odrzucenia kwotowe lub brakujące dane). Przeczesujemy XML w poszukiwaniu taga `<TxSts>` i jeśli go znajdziemy, to wyciągamy jego wartość, by podjąć decyzję co dalej z pieniędzmi.

### Wspólna pułapka ułatwiająca integrację: Określanie Odbiorcy
Zarówno XML jak i JSON z Elixir-PZ wymagają podania kodu banku odbiorcy (`ReceiverBankId` w JSON, bądź w tagach `<CdtrAgt><FinInstnId><BICFI>...` w XML).
W naszym kodzie, przed wygenerowaniem ładunku, sprawdzamy **pierwsze 6 cyfr numeru rachunku docelowego** (IBAN). 
Wdrożyliśmy sztywny switch:
- Zaczyna się od `111111` -> wysyłamy na `BANK_A`
- Zaczyna się od `222222` -> wysyłamy na `BANK_B`
- Zaczyna się od `333333` -> wysyłamy na `BANK_C`

---

## 2. Polling i Śledzenie Statusów (Express Elixir)

Gdy zlecamy Express Elixir przez port 8082, nasz klient nie wie od razu, czy system przyjął ten przelew z powodzeniem, czy rachunek docelowy go odrzucił (systemy expressowe działają w tle). Środki na koncie ulegają u nas zablokowaniu (zamrożeniu), ale jeszcze ich całkowicie nie odejmujemy.

Musieliśmy wdrożyć robota odpytującego system centralny.
👉 **Plik:** `src/transfers/management/commands/consume_express_elixir.py`

### Jak to napisaliśmy:
1. Użyliśmy skryptu narzędziowego Django (`BaseCommand`), który działa w nieskończonej pętli `while True`. Zwykłe `time.sleep(2)` puszcza iterację co 2 sekundy (Express Elixir jest szybki, więc częsty polling ma sens).
2. Nasz "robot" wykonuje po kolei 3 pociągnięcia GET:
   - `GET 8082/api/express/payments/status/PROCESSED`
   - `GET 8082/api/express/payments/status/REJECTED`
   - `GET 8082/api/express/payments/status/BLOCKED`
3. API centrali zwraca nam JSON-y z numerami przelewów, w których zmienił się status. Wyciągamy `paymentId` i wywołujemy naszą bazę danych (`Transfer.objects.get(id=paymentId)`).

### Bezpieczeństwo transakcyjne bazy danych (Najważniejsze)
Jeśli Twój kolega ma problemy na etapie księgowania, musi uważnie przeczytać to rozwiązanie.
W pętli pobierającej status wdrożyliśmy mechanizm ryglowania wierszy w bazie (`SELECT FOR UPDATE`), z wykorzystaniem `transaction.atomic()`.

```python
with transaction.atomic():
    transfer = Transfer.objects.select_for_update().get(id=payment_id, system_route='EXPRESS_ELIXIR')
    account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
```

Gdy przychodzi status `COMPLETED` z centrali:
Odejmujemy kwotę z atrybutu `blocked_funds` (zamrożone) na koncie i odejmujemy ją również ze stałego salda `balance`. Zapisujemy przelew jako ukończony.

Gdy przychodzi status `FAILED` / `REJECTED`:
Odejmujemy kwotę TYLKO z atrybutu `blocked_funds`. Pieniądze w `balance` pozostają nietknięte. W ten sposób błędny przelew Expressowy po prostu odblokowuje środki na koncie z powrotem.

### Dlaczego to działa niezawodnie?
Zastosowaliśmy transakcje na poziomie bazy danych i podział salda na "dostępne" (`balance - blocked_funds`) i "rzeczywiste". Gdyby aplikacja uległa awarii w połowie przetwarzania, żadna blokada się nie odblokuje bez odpowiedniego wpisu, a my unikniemy błędu podwójnego zablokowania lub wydania tych samych pieniędzy.

Niech Twój kolega koniecznie upewni się, że jego odpytywacz (robot Express Elixir) dokonuje zmian na koncie użytkownika pod ścisłą blokadą transakcyjną!
