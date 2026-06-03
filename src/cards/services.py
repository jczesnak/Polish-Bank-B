import grpc
import time
import json
import hmac
import hashlib
from django.conf import settings
from . import card_pb2
from . import card_pb2_grpc
from .models import PaymentCard

class CardIntegrationService:
    def __init__(self):
        self.channel = grpc.insecure_channel('card-provider:50051')
        self.stub = card_pb2_grpc.CardProviderStub(self.channel)

    def order_card(self, account):
        # 1. Przygotowanie słownika z danymi do podpisu
        body = {
            "user_id": str(account.user.id),
            "account_id": str(account.id),
            "card_type": "VIRTUAL",
            "initial_balance": 0.0,
        }

        timestamp = str(int(time.time()))
        
   
        body_json = json.dumps(body, separators=(',', ':'), sort_keys=True)
        payload_to_sign = timestamp + body_json
        
        api_secret = settings.CARDS_API_SECRET.encode('utf-8')
        

        signature = hmac.new(api_secret, payload_to_sign.encode('utf-8'), hashlib.sha256).hexdigest()

        # 4. Budowanie żądania gRPC
        request = card_pb2.CreateCardRequest(
            user_id=body["user_id"],
            account_id=body["account_id"],
            card_type=body["card_type"],
            initial_balance=body["initial_balance"],
            api_key=settings.CARDS_API_KEY,
            signature=signature,
            timestamp=timestamp
        )
        
        try:
            response = self.stub.CreateCard(request)
            
            card = PaymentCard.objects.create(
                account=account,
                card_number=response.full_pan,
                external_card_id=response.card_token,
                masked_number=response.masked_pan
            )
            
            return {
                "success": True,
                "card": card,
                "masked_number": response.masked_pan,
                "expiry_date": f"{response.expiry_month:02d}/{response.expiry_year}",
                "cvv": response.cvv
            }
        except grpc.RpcError as e:
            return {
                "success": False,
                "error_code": str(e.code()),
                "details": e.details()
            }
        
    def block_card(self, card_token, reason="Zablokowana przez użytkownika"):
        """Wysyła sygnał dezaktywacji karty do systemu zewnętrznego."""
        request = card_pb2.BlockCardRequest(
            card_token=card_token,
            reason=reason
        )
        
        try:
            response = self.stub.BlockCard(request)
            return {
                "success": response.success,
                "message": response.message
            }
        except grpc.RpcError as e:
            return {
                "success": False,
                "error_code": str(e.code()),
                "details": e.details()
            }
        

    def get_card_details(self, card_token):
        """Pobiera pełne dane karty używając istniejącego RPC GetFullPan."""
        request = card_pb2.GetCardRequest(card_token=card_token)
        
        try:
            response = self.stub.GetFullPan(request)
            return {
                "success": True,
                "full_pan": response.full_pan,
                "cvv": response.cvv,
                "expiry_date": f"{response.expiry_month:02d}/{response.expiry_year}"
            }
        except grpc.RpcError as e:
            return {
                "success": False,
                "error_code": str(e.code()),
                "details": e.details()
            }