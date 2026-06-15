import time
import json
import hmac
import hashlib
import requests
from django.conf import settings
from .models import PaymentCard

class CardIntegrationService:
    def __init__(self):
        self.base_url = getattr(settings, 'INTEGRATIONS_CARDS_URL', 'http://cards_gateway_app:8000')
        self.api_key = getattr(settings, 'CARDS_API_KEY', 'bank-key-pl-b')
        self.api_secret = getattr(settings, 'CARDS_API_SECRET', 'secret-pl-b-hmac')

    def _sign_request(self, body: dict) -> tuple[str, str]:
        timestamp = str(int(time.time()))
        body_json = json.dumps(body, separators=(',', ':'), sort_keys=True)
        payload_to_sign = timestamp + body_json
        
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            payload_to_sign.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature, timestamp

    def _get_headers(self, body: dict) -> dict:
        signature, timestamp = self._sign_request(body)
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
            "X-Signature": signature,
            "X-Timestamp": timestamp
        }

    def order_card(self, account, card_type="VIRTUAL", initial_balance=0.0):
        body = {
            "user_id": str(account.user.id),
            "account_id": str(account.id),
            "card_type": card_type,
            "initial_balance": initial_balance,
        }
        
        headers = self._get_headers(body)
        url = f"{self.base_url}/api/v1/cards/issue"
        
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                card = PaymentCard.objects.create(
                    account=account,
                    card_number=data.get("full_pan"),
                    external_card_id=data.get("card_token"),
                    masked_number=data.get("masked_pan")
                )
                
                return {
                    "success": True,
                    "card": card,
                    "masked_number": data.get("masked_pan"),
                    "expiry_date": f"{data.get('expiry_month', 0):02d}/{data.get('expiry_year', 0)}",
                    "cvv": data.get("cvv")
                }
            else:
                return {
                    "success": False,
                    "error_code": str(response.status_code),
                    "details": response.text
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error_code": "CONNECTION_ERROR",
                "details": str(e)
            }

    def unblock_card(self, card_token, reason="Odblokowana przez użytkownika"):
        body = {
            "status": "ACTIVE",
            "reason": reason
        }
        
        headers = self._get_headers(body)
        url = f"{self.base_url}/api/v1/cards/{card_token}/status"
        
        try:
            response = requests.patch(url, json=body, headers=headers, timeout=10)
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Status updated successfully"
                }
            else:
                return {
                    "success": False,
                    "error_code": str(response.status_code),
                    "details": response.text
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error_code": "CONNECTION_ERROR",
                "details": str(e)
            }

    def block_card(self, card_token, reason="Zablokowana przez użytkownika"):
        body = {
            "status": "BLOCKED",
            "reason": reason
        }
        
        headers = self._get_headers(body)
        url = f"{self.base_url}/api/v1/cards/{card_token}/status"
        
        try:
            response = requests.patch(url, json=body, headers=headers, timeout=10)
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": "Status updated successfully"
                }
            else:
                return {
                    "success": False,
                    "error_code": str(response.status_code),
                    "details": response.text
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error_code": "CONNECTION_ERROR",
                "details": str(e)
            }

    def get_card_details(self, card_token):
        # Pobieramy dane ogólne z podstawowego endpointu
        url_status = f"{self.base_url}/api/v1/cards/{card_token}"
        # Pobieramy pełne dane z administracyjnego endpointu
        url_full = f"{self.base_url}/api/v1/cards/{card_token}/full-pan"
        headers_admin = {"X-Admin-Key": "admin-secret-key-2026"}
        
        try:
            res_status = requests.get(url_status, timeout=10)
            res_full = requests.get(url_full, headers=headers_admin, timeout=10)
            
            if res_status.status_code == 200 and res_full.status_code == 200:
                data_status = res_status.json()
                data_full = res_full.json()
                
                return {
                    "success": True,
                    "status": data_status.get("status"),
                    "card_type": data_status.get("card_type"),
                    "balance": data_status.get("balance"),
                    "daily_limit": data_status.get("daily_limit"),
                    "full_pan": data_full.get("full_pan"),
                    "masked_pan": data_full.get("masked_pan"),
                    "cvv": data_full.get("cvv"),
                    "expiry_date": f"{data_full.get('expiry_month', 0):02d}/{data_full.get('expiry_year', 0)}"
                }
            else:
                return {
                    "success": False,
                    "error_code": f"STATUS: {res_status.status_code}, FULL: {res_full.status_code}",
                    "details": "Nie udało się pobrać wszystkich danych karty."
                }
        except requests.exceptions.RequestException as e:
            return {
                "success": False,
                "error_code": "CONNECTION_ERROR",
                "details": str(e)
            }

    def activate_card(self, card_token):
        url = f"{self.base_url}/api/v1/cards/{card_token}/activate"
        body = {"activated_by": "customer"}
        headers = self._get_headers(body)
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            if response.status_code == 200:
                return {"success": True, "message": "Karta została aktywowana."}
            else:
                return {"success": False, "error_code": str(response.status_code), "details": response.text}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error_code": "CONNECTION_ERROR", "details": str(e)}

    def topup_prepaid(self, card_token, amount):
        url = f"{self.base_url}/api/v1/cards/{card_token}/topup"
        body = {"amount": float(amount), "currency": "PLN"}
        headers = self._get_headers(body)
        try:
            response = requests.post(url, json=body, headers=headers, timeout=10)
            if response.status_code == 200:
                return {"success": True, "new_balance": response.json().get("new_balance")}
            else:
                return {"success": False, "error_code": str(response.status_code), "details": response.text}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error_code": "CONNECTION_ERROR", "details": str(e)}

    def dev_simulate_shipping(self, card_token):
        url = f"{self.base_url}/api/v1/cards/{card_token}/lifecycle"
        headers = {"X-Admin-Key": "admin-secret-key-2026"}
        try:
            res1 = requests.patch(url, headers=headers, json={"new_status": "PRODUCING", "changed_by": "dev"}, timeout=10)
            res2 = requests.patch(url, headers=headers, json={"new_status": "SHIPPED", "changed_by": "dev"}, timeout=10)
            if res2.status_code == 200:
                return {"success": True, "message": "Zasymulowano wysyłkę karty."}
            else:
                return {"success": False, "error_code": str(res2.status_code), "details": res2.text}
        except requests.exceptions.RequestException as e:
            return {"success": False, "error_code": "CONNECTION_ERROR", "details": str(e)}