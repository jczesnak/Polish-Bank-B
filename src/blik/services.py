import uuid

import requests
from django.conf import settings
from django.utils import timezone


class KlikError(Exception):
    """Błąd zwrócony przez API KLIK (envelope {"error": {...}}).

    Niesie `code` i `message` z KLIK oraz oryginalny `status_code` HTTP,
    dzięki czemu widoki mogą mapować np. 404_ALIAS_NOT_FOUND na przyjazny
    komunikat zamiast generycznego 502.
    """

    def __init__(self, status_code: int, code: str = '', message: str = ''):
        self.status_code = status_code
        self.code = code
        self.message = message or f'KLIK zwrócił HTTP {status_code}'
        super().__init__(f'{code or status_code}: {self.message}')


class KlikService:
    """Klient HTTP do systemu KLIK (operator płatności mobilnych).

    Bazowy URL wskazuje na root KLIK (np. http://klik:8000); ścieżki API
    (/api/v1/...) dokładamy tutaj. Autoryzacja: nagłówek X-KLIK-Bank-Api-Key
    wydany bankowi przy onboardingu w KLIK.
    """

    def __init__(self):
        self.base_url = settings.KLIK_BASE_URL.rstrip('/')
        self.api_key = settings.BLIK_API_KEY
        self.timeout = getattr(settings, 'KLIK_HTTP_TIMEOUT', 10)

    def _headers(self):
        return {
            'X-KLIK-Bank-Api-Key': self.api_key,
            'Idempotency-Key': str(uuid.uuid4()),
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        url = f'{self.base_url}/api/v1{path}'
        try:
            response = requests.request(
                method,
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise KlikError(502, 'KLIK_UNREACHABLE', f'KLIK nieosiągalny: {exc}') from exc

        if response.status_code >= 400:
            body = {}
            if response.content:
                try:
                    body = response.json()
                except ValueError:
                    body = {}
            err = body.get('error', {}) if isinstance(body, dict) else {}
            raise KlikError(
                response.status_code,
                err.get('code', f'HTTP_{response.status_code}'),
                err.get('message', ''),
            )

        if response.content:
            try:
                return response.json()
            except ValueError:
                return {}
        return {}

    # ----- C2B (płatność kodem) ------------------------------------------
    def generate_code(self, user_id: str, zone: str = 'PL') -> dict:
        return self._request('POST', '/codes/generate', {'user_id': user_id, 'zone': zone})

    def confirm_payment(self, transaction_id: str, decision: str, reject_reason: str = None) -> dict:
        # KLIK wymaga pola `status` (ACCEPTED/REJECTED).
        payload = {'transaction_id': transaction_id, 'status': decision}
        if decision == 'ACCEPTED':
            payload['authorization_timestamp'] = timezone.now().isoformat()
        elif decision == 'REJECTED' and reject_reason:
            payload['reject_reason'] = reject_reason
        return self._request('POST', '/payments/confirm', payload)

    def get_transaction_status(self, transaction_id: str) -> dict:
        return self._request('GET', f'/payments/status/{transaction_id}')

    # ----- P2P (przelew na telefon) --------------------------------------
    def register_alias(self, phone: str, iban: str, zone: str = 'PL') -> dict:
        return self._request('POST', '/aliases/register', {'phone': phone, 'iban': iban, 'zone': zone})

    def lookup_alias(self, phone: str) -> dict:
        return self._request('GET', f'/aliases/lookup/{phone}')

    def delete_alias(self, phone: str) -> dict:
        return self._request('DELETE', f'/aliases/{phone}')
