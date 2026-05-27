import uuid
import requests
from django.conf import settings
from django.utils import timezone


class KlikService:
    def __init__(self):
        self.base_url = settings.KLIK_BASE_URL.rstrip('/')
        self.api_key = settings.BLIK_API_KEY

    def _headers(self):
        return {
            'X-KLIK-Bank-Api-Key': self.api_key,
            'Idempotency-Key': str(uuid.uuid4()),
            'Content-Type': 'application/json',
        }

    def generate_code(self, user_id: str, zone: str = 'PL') -> dict:
        response = requests.post(
            f'{self.base_url}/api/v1/codes/generate',
            json={'user_id': user_id, 'zone': zone},
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def confirm_payment(self, transaction_id: str, decision: str, reject_reason: str = None) -> dict:
        payload = {'transaction_id': transaction_id, 'status': decision}
        if decision == 'ACCEPTED':
            payload['authorization_timestamp'] = timezone.now().isoformat()
        elif decision == 'REJECTED' and reject_reason:
            payload['reject_reason'] = reject_reason

        response = requests.post(
            f'{self.base_url}/api/v1/payments/confirm',
            json=payload,
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def get_transaction_status(self, transaction_id: str) -> dict:
        response = requests.get(
            f'{self.base_url}/api/v1/payments/status/{transaction_id}',
            headers=self._headers(),
            timeout=10,
        )
        response.raise_for_status()
        return response.json()
