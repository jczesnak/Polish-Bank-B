# Integracja Przelewów Międzynarodowych SWIFT (ISO 20022) - Przewodnik dla Backend Developera

Niniejszy dokument opisuje techniczne i biznesowe wytyczne dla zespołu backendowego, niezbędne do wdrożenia komunikacji z siecią SWIFT w celu realizacji przelewów międzynarodowych i walutowych.

## 1. Komunikaty SWIFT (Standard ISO 20022)
Systemy SWIFT wycofują stare komunikaty tekstowe (serii MT, np. MT103). Nowoczesny backend musi generować oraz parsować wiadomości w formacie XML (ISO 20022). Podstawowym komunikatem dla transferu środków zleconego przez klienta jest **`pacs.008` (Customer Credit Transfer)**. 

Każda wygenerowana przez backend wiadomość musi obowiązkowo zawierać:
* **UETR (Unique End-to-end Transaction Reference)**: Unikalny UUIDv4 przypisany do transakcji, niezbędny do systemu śledzenia SWIFT GPI (Global Payments Innovation).
* Prawidłowe tagi `<InstdAmt>` (kwota zlecona) oraz zdefiniowany kod opcji kosztowej (`OUR`, `SHA`, `BEN` mapowane na odpowiednie tagi w węźle `<ChrgBr>`).

---

## 2. Architektura Bankowości Korespondenckiej (Konta Nostro/Loro)

Przelewy SWIFT nie polegają na bezpośrednim wysyłaniu środków. Działają one w oparciu o sieć wzajemnych kont powierniczych (banki utrzymują konta u siebie nawzajem). Rozważmy analizowaną ścieżkę:
`PLBKPL01XXX (My) → UKBKGB01XXX → UKBKGB02XXX → USBKUS02XXX → USBKUS01XXX`

**Jak wygląda przepływ w backendzie:**
1. **Start w Polskim Banku (PLBKPL01XXX)**: Pobierasz od klienta środki w PLN z jego konta na podstawie własnego, sztywnego kursu wymiany (spreadu). W systemie księgowym ściągasz z konta w PLN, a na technicznym koncie walutowym notujesz zobowiązanie.
2. **Kierowanie (Routing)**: Twój bank nie ma bezpośredniego konta w amerykańskim banku docelowym (`USBKUS`). Backend decyduje (na podstawie tablic SSI - Standard Settlement Instructions), że prześle komunikat do pierwszego korespondenta – banku brytyjskiego (`UKBKGB01`).
3. **Nostro/Loro w UK**: Bank brytyjski pobiera należność ze środków (konta Loro), które bank polski trzyma u niego, ewentualnie przeliczając walutę operacyjną (np. na GBP). Następnie wysyła polecenie dalej do `UKBKGB02`.
4. **Przejście na USA**: Drugi bank w UK używa swojego konta w banku amerykańskim (`USBKUS02`), gdzie przewalutowuje środki na docelowe **USD**.
5. **Rozliczenie finalne (Settlement)**: Komunikat SWIFT informuje o dyspozycji operacji. Wyrównanie sald między bankami często odbywa się w tle przy użyciu wielkich lokalnych systemów rozrachunkowych. Przykładowo, na samym końcu, amerykańscy korespondenci przeleją sobie fizycznie dolary używając **ACH** lub **Fedwire**, a europejscy użyją **SEPA** lub **BACS**.

---

## 3. Opcje Kosztowe (Kto płaci prowizje?)

Przewalutowanie to tylko część opłat. Ponieważ transakcja przechodzi przez 3 banki po drodze (tzw. banki pośredniczące), mogą one chcieć potrącić prowizję. Backend musi oprogramować logikę dla pola wyboru kosztów z frontendu:

* **OUR (Pokrywa Nadawca)**: Klient w Polsce musi zapłacić dodatkową zryczałtowaną opłatę (np. 100 PLN extra z konta). W zamian, korespondenci po drodze **nie mogą** potrącić nic z docelowej kwoty (np. z 20.00 USD). Odbiorca musi dostać dokładnie 20.00 USD.
* **SHA (Dzielone - Shared)**: Klient płaci jedynie opłatę pobraną przez bank polski za wysłanie SWIFT. Banki po drodze (np. amerykański korespondent) potrącą prowizję bezpośrednio z kwoty przelewu. Odbiorca otrzyma np. 12.00 USD (zamiast 20.00 USD).
* **BEN (Pokrywa Odbiorca - Beneficiary)**: Zlecający z Polski nie płaci żadnych opłat bankowych za realizację. Wszystkie prowizje (polskiego banku i wszystkich pośredników) są wycinane z przesyłanej kwoty. Odbiorca może otrzymać znacznie pomniejszoną kwotę.

---

## 4. Odrzucenia i Zwroty (Return)

Co musi zrobić backend, jeśli docelowy bank amerykański stwierdzi, że *"Konto jest zamknięte / Nie istnieje"*?
Zgodnie z protokołem SWIFT, transakcja wraca do nadawcy jako nowy komunikat zwrotny (z odwróconym nadawcą i odbiorcą, często pacs.004 lub camt.056/pacs.002 z odpowiednim Reason Code).

**Bardzo ważne dla implementacji Backendowej (Ryzyko Kursowe):**
1. Zwrot odbywa się w walucie obcej, zazwyczaj po kilku lub kilkunastu dniach.
2. Backend, przyjmując zwrot, **musi** przewalutować te środki z powrotem na PLN po kursie **z dnia zwrotu**, a NIE po kursie z dnia wysłania.
3. W efekcie, ze względu na zmianę kursu walutowego, klient otrzyma z powrotem inną kwotę w PLN niż początkowo wysłał. Oraz koszty zryczałtowane pobrane za wysłanie nie są mu zwracane! Backend musi oprogramować taką księgowość operacyjną.

---

## 5. Zadania Implementacyjne (To-Do)

Aby obsłużyć SWIFT, backend musi dostarczyć:
1. **Silnik Walutowy (FX Engine)**: Tablice aktualnych kursów rynkowych + narzut bankowy (spread). Przeliczanie kwot na bieżąco w obu kierunkach dla zwrotów.
2. **Generator UETR**: Przypinany do każdego zlecenia w celu transparentności (SWIFT gpi).
3. **Zarządzanie SSI**: Mechanizm "trasowania" (Routing), w którym zapiszecie zasady, z jakim bankiem z Waszej sieci korespondentów rozmawiacie dla konkretnych walut i regionów.
4. **Parser ISO 20022**: Bibliotekę XML (np. wspieraną przez schematy XSD) mapującą Wasze lokalne modele bazodanowe na węzły `<CdtTrfTxInf>`, `<IntrBkSttlmAmt>` czy `<ChrgBr>`.

---

## 6. Integracja z lokalnym Symulatorem SWIFT (SWIFT-Aplikacje-Biznesowe)

W naszym ekosystemie działa już instancja **SWIFT Middleware Simulation** pod adresem `http://localhost:3000`. Nasz bank operuje prawdopodobnie pod kodem BIC **`PLBKPL01XXX`**.
Aby podłączyć backend naszego banku (Polish-Bank-B) do tej sieci, zespół musi wykonać następujące kroki:

### A. Wysyłanie przelewów (Z naszego banku w świat)
1. **Autoryzacja (OAuth2)**: Zanim wyślemy komunikat, nasz backend musi pobrać token:
   `POST http://localhost:3000/auth/token` z payloadem `client_id=test-client` & `client_secret=test-secret`.
2. **Generowanie XML**: Po wpisaniu danych przez klienta w UI, backend składa komunikat `<Document xmlns="urn:iso...">` ustawiając `<DbtrAgt><FinInstnId><BICFI>PLBKPL01XXX</BICFI>...`.
3. **Wysyłka**: Uderzamy na `POST http://localhost:3000/swift/message` z wygenerowanym plikiem XML i nagłówkiem `Authorization: Bearer <TOKEN>`.
4. **Anulowanie**: Symulator posiada opóźnienie (`FORWARD_DELAY_SECONDS`). Jeśli nasz klient kliknie "Anuluj" zaraz po wysłaniu przelewu zagranicznego, backend ma okno czasowe by wysłać `POST http://localhost:3000/swift/cancel/<UETR>`.

### B. Odbieranie przelewów (Z innych banków do naszego klienta)
W sieci symulatora działa "Mock-Bank" dla `PLBKPL01XXX` na porcie `3001`. Aby przeprowadzić pełną integrację, musimy go **zastąpić** naszym serwerem!
1. Należy zmienić konfigurację symulatora (`config.py`), aby adres dla `PLBKPL01XXX` nie kierował na `localhost:3001`, lecz na backend Polish-Bank-B (np. `localhost:8080/api/swift/receive`).
2. Nasz backend musi wystawić endpoint `POST /api/swift/receive`, który będzie przyjmował komunikaty XML od innych banków w sieci.
3. Gdy uderzy do nas symulator, wyciągamy z XML pole `<CdtrAcct><Id><IBAN>` (konto naszego klienta) oraz `<InstdAmt>` (kwotę), dodajemy odpowiednią kwotę do salda w naszej bazie i wyrzucamy do symulatora zwrotkę `202 Accepted`.
