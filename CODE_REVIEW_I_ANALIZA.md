# Code Review: Konto Junior (Polish-Bank-B)

Przeanalizowałem strukturę bazy danych (`models.py`), widoki (`views.py`) oraz serializatory odpowiedzialne za najnowszą funkcjonalność konta Junior stworzoną przez Twojego znajomego.

## Mocne strony rozwiązania (Pochwała)
Twój kolega naprawdę nieźle radzi sobie z mechanizmami bazodanowymi w Django.
1. **Bezpieczeństwo współbieżności:** Przy doładowywaniu konta dziecka przez rodzica (`JuniorTopUpView`) oraz akceptacji wniosków, poprawnie i konsekwentnie stosuje `transaction.atomic()` w połączeniu z `select_for_update()`. To bardzo chroni bank przed "Race Conditions" i podwójnym wydawaniem tych samych pieniędzy z konta rodzica w jednym momencie.
2. **Nowoczesne User Experience:** Zakładając konto dla dziecka (widok `JuniorListView.post`), oprócz wygenerowania profilu, aplikacja w tej samej transakcji wykonuje asynchroniczny strzał do integracji kart i **automatycznie zamawia dla Juniora kartę przedpłaconą** (PREPAID). Świetny ruch biznesowy!
3. **Prawidłowy przepływ decyzyjny:** Wprowadzenie dedykowanej tabeli `JuniorTransferRequest` jako poczekalni (statusy `PENDING`, `APPROVED`, `REJECTED`) idealnie wpisuje się w standardy nadzoru rodzicielskiego w aplikacjach bankowych.

## Zagrożenia (Do natychmiastowej poprawki)
> [!WARNING]
> **Krytyczny błąd w zatwierdzaniu przelewów zewnętrznych (ParentTransferRequestApproveView)!**
> 
> Zauważyłem, że kiedy rodzic akceptuje wniosek dziecka o przelew (metoda POST), backend zawsze wymusza trasowanie wewnętrzne:
> ```python
> Transfer.objects.create(
>     sender_account=locked_junior,
>     recipient_iban=req.recipient_iban,
>     amount=req.amount,
>     system_route='INTERNAL', # BŁĄD!
>     status='COMPLETED',      # BŁĄD!
> )
> ```
> **Skutek:** Jeśli dziecko wpisze IBAN banku zewnętrznego (np. "Banku C"), to po akceptacji ze strony rodzica pieniądze po prostu **znikną z konta dziecka**, dostaną status `COMPLETED`, ale **nigdy nie zostaną wysłane do infrastruktury Elixir / Sorbnet / Express**. Backend zapisze je jako "wewnętrzne" i porzuci na poziomie bazy danych. Znajomy musi zintegrować akceptację przelewów juniora z routerem przelewów, który decyduje, jaki to system rozliczeniowy w zależności od prefiksu IBAN.

---

# Analiza Zmian w Systemach Zewnętrznych

Zgodnie z prośbą, zaktualizowałem (ściągnąłem) lokalne gałęzie z trzech systemów i przestudiowałem historie commitów.

## 1. System Kart Płatniczych (Karty-Platnicze-Aplikacje-Biznesowe)
Najnowsze zawirowania wokół `docker-compose.yaml` (przez które nie mogłeś spullować zmian) dotyczyły wdrożenia **"Izolacji Banków"**.

Co ważniejsze jednak, system wprowadził mocne uszczelnienie bezpieczeństwa na bramce API.
* **Zmiana:** Wymuszenie podpisów HMAC i ochrony przed Replay Attacks na endpointach doładowywania, aktywacji i statusu karty. Wcześniej symulator kart wymagał od banków podpisów kryptograficznych tylko przy wydawaniu plastiku (`/issue`). Teraz każda akcja modyfikująca kartę zmusza nas do dołączenia poprawnego nagłówka `X-Signature` wraz z `X-Timestamp`.
* **Wpływ na Polish-Bank-B:** **Jesteśmy bezpieczni!** Sprawdziłem naszą klasę `CardIntegrationService` w kodzie i my, zachowując dobre praktyki programistyczne, *od początku istnienia projektu* generowaliśmy poprawne sygnatury w funkcji `_get_headers()` i dolepialiśmy je do każdego strzału (w tym do `topup_prepaid`). Nic u nas nie wybuchnie po wejściu tej aktualizacji na środowisko produkcyjne!

## 2. System Elixir-PZ
Zespół zaimplementował dwa ważne ficzery ułatwiające uruchamianie i obsługę awaryjną ich symulatora:
* **Healthchecki Baz Danych w Dockerze:** Kontenery aplikacji Springowych teraz ładnie czekają na wstanie baz PostgreSQL. Wcześniej potrafiły sypać błędami na start.
* **GRIDLOCK (Zatory Płatnicze) w Express Elixirze:** Jeśli podczas wysyłania Express Elixira zabraknie nam pieniędzy na koncie zabezpieczającym w NBP, nasz przelew zostanie oflagowany jako `GRIDLOCK_HELD`. Oprogramowano logikę, która samodzielnie wyliczy minimalne zasilenie, jakiego bank potrzebuje, a po uzupełnieniu płynności (np. przez Sorbnet) wszystkie wstrzymane przelewy zostaną z automatu "puszczone" do adresatów. Skonfigurowano też timeout (bank jest banowany po przekroczeniu czasu na zebranie płynności).

## 3. System KLIK-payments (BLIK)
W module KLIK weszły głównie drobne "prace domowe":
* Saserwowano poprawne pliki statyczne dla ich wbudowanego Panelu Administratora (wcześniej GUI mogło nie ładować styli).
* Dodano do dokumentacji oraz przetestowano środowiska **CHAPS** i **TARGET**. Wygląda na to, że symulator KLIKa (polski standard) będzie rozwijany w stronę możliwości testowania zagranicznych i europejskich standardów rozliczeniowych. Z punktu widzenia Polish-Bank-B nie wprowadza to na ten moment nowych obowiązków integracyjnych.
