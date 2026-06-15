# Integracja Systemu Przelewów (Elixir, Express Elixir, Sorbnet) - Przewodnik dla Backend Developera

Niniejszy dokument opisuje techniczne oraz biznesowe aspekty niezbędne do poprawnego zintegrowania modułu przelewów zrealizowanego we frontendzie aplikacji (Joker Bank) z systemami rozliczeniowymi KIR (Krajowa Izba Rozliczeniowa) oraz NBP (Narodowy Bank Polski).

## 1. Kontrakt API (Wymagany Payload)

Gdy użytkownik zleca przelew w komponencie transferu, frontend wysyła żądanie na endpoint:
`POST /api/transfers`

Oczekiwany w backendzie payload z frontendu wygląda następująco:
```json
{
  "sender_account": "acc_09876",
  "recipient_iban": "PL 11 1140 2004 0000 3002 0123 4567",
  "recipient_name": "Jan Kowalski",
  "amount": 1500.00,
  "title": "Zaliczka za projekt",
  "transfer_type": "internal | standard | express | sorbnet"
}
```

---

## 2. Architektura Trasowania Przelewów (Routing)

Backend musi pełnić rolę "routera" sprawdzającego flagę `transfer_type` i w zależności od niej przekierowywać płatność do odpowiedniej bramki lub kolejki.

### A. Wewnętrzny (`internal`)
* **Architektura**: Baza danych banku (zamknięty system).
* **Przepływ**: Wykonanie transakcji bazodanowej zgodnej ze standardem ACID, która pomniejsza saldo nadawcy i natychmiast powiększa saldo odbiorcy.
* **Czas**: Natychmiastowo.
* **Opłaty**: Zawsze darmowe.

### B. Standardowy Elixir (`standard`)
* **Architektura**: System Elixir zarządzany przez KIR.
* **Przepływ**: Transakcje typu `standard` zlecone przez klientów nie są wysyłane z banku pojedynczo. Backend musi zbierać zlecenia w tzw. "paczki rozliczeniowe" i przesyłać je do KIR zgodnie z harmonogramem sesji.
* **Sesje Rozliczeniowe**: Istnieją 3 sesje wychodzące dziennie (np. 9:30, 13:30, 16:00). Jeśli klient zleci przelew po godzinie 16:00, backend musi nadać mu status `PENDING` (oczekujący) i ująć go w paczce o 9:30 rano następnego dnia roboczego.
* **Księgowanie**: Po przeprocesowaniu paczki powrotnej z KIR, backend musi zmienić status przelewu na `COMPLETED`.

### C. Express Elixir (`express`)
* **Architektura**: System przelewów natychmiastowych KIR (API REST/SOAP).
* **Przepływ**: System działa w architekturze 24/7. Backend musi odpytać KIR natychmiast po zleceniu przelewu.
* **Księgowanie**: Pieniądze są blokowane na koncie nadawcy. Po otrzymaniu synchronicznego potwierdzenia z KIR, operacja jest finalizowana (status `COMPLETED`). Czas oczekiwania to maksymalnie kilkanaście sekund.
* **Walidacja na Froncie**: Frontend w locie wyświetla informację "Zaksięgujemy natychmiast", jednak backend wciąż musi pobrać ewentualną zdefiniowaną prowizję (w wielu bankach jest darmowy, zależy od Taryfy Opłat i Prowizji).

### D. System SORBNET (`sorbnet`)
* **Architektura**: System RTGS prowadzony bezpośrednio przez Narodowy Bank Polski (NBP).
* **Przepływ**: Wykorzystywany głównie do bardzo dużych kwot lub pilnych rozliczeń urzędowych. Nie posiada harmonogramu sesji — przelewy wpadają "pojedynczo" w czasie rzeczywistym.
* **Ograniczenia czasowe**: Działa tylko w dni robocze od 8:00 do 16:00. Backend musi wstrzymać realizację zlecenia wysłanego w weekend.
* **Opłaty**: Sorbnet u operatora zawsze wiąże się z ryczałtową opłatą. Backend musi utworzyć **dwie transakcje**: jedną dla przelewu, a drugą (dodatkową) dla pobrania prowizji (np. kilkadziesiąt złotych) od klienta. Frontend UI już wyświetla informację "Prowizja 1 PLN" jako przykład - pamiętaj zsynchronizować to z cennikiem banku!

---

## 3. Dodatkowe Systemy Obowiązkowe po Stronie Backendu

Aby system bankowy był zgodny z prawem oraz oczekiwaniami nowoczesnego UI, backend musi również implementować:

1. **Bezwzględna Walidacja NRB**: Chociaż frontend wykonuje podstawową walidację, backend MUSI wykonać twardą walidację numeru konta w formacie NRB (26 cyfr), sprawdzając sumę kontrolną Modulo 97.
2. **Procedury AML (Anti-Money Laundering)**: Zanim przelew zostanie wysłany poza bank (szczególnie zagraniczny lub Sorbnet wysokokwotowy), backend musi przepuścić payload przez silnik AML/KYC. Status transakcji może zostać wstrzymany na `HELD_FOR_REVIEW`.
3. **Potwierdzenia PDF (Generator)**: Endpoint `/api/transfers/{id}/confirmation` powinien generować w locie oficjalny plik PDF dla klienta (tzw. elektroniczne potwierdzenie wykonania transakcji), ze stemplem czasowym oraz referencją banku.
4. **Identyfikator Transakcji (UETR)**: Dla nowszych systemów bankowych, każdy przelew powinien posiadać śledzony identyfikator Unique End-to-end Transaction Reference (UETR).
