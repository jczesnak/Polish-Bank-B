import requests
import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from rest_framework.exceptions import APIException
from .models import Transfer
import xml.etree.ElementTree as ET

def check_aml(transfer) -> bool:
    """
    Mock systemu Anti-Money Laundering.
    Zwraca True jeśli przelew jest czysty, False jeśli został zablokowany.
    W przypadku zablokowania zmienia status przelewu na AML_SUSPENDED.
    """
    suspicious_keywords = ["pranie", "okup", "haracz", "krypto", "crypto", "hack", "bomb", "drugs"]
    
    title_lower = transfer.title.lower()
    is_suspicious_title = any(kw in title_lower for kw in suspicious_keywords)
    
    # Przelewy powyżej 50 000 są podejrzane
    is_high_amount = transfer.amount >= Decimal('50000.00')
    
    if is_suspicious_title or is_high_amount:
        transfer.status = 'AML_SUSPENDED'
        transfer.save(update_fields=['status'])
        return False
        
    return True

ELIXIR_API_URL = "http://host.docker.internal:8081/api/elixir/payments"

class ElixirIntegrationService:
    @staticmethod
    def send_transfer(transfer: Transfer):
        """
        Wysyła przelew do zewnętrznego systemu Elixir-PZ w formacie XML.
        """
        sender_bank_id = "BANK_B"
        
        # Wyznaczamy receiverBankId na podstawie prefiksu IBAN
        receiver_iban_prefix = transfer.recipient_iban[:6]
        if receiver_iban_prefix == "111111":
            receiver_bank_id = "BANK_A"
        elif receiver_iban_prefix == "222222":
            receiver_bank_id = "BANK_B"
        elif receiver_iban_prefix == "333333":
            receiver_bank_id = "BANK_C"
        else:
            receiver_bank_id = "BANK_A" # Domyślnie BANK_A dla pozostałych

        from datetime import datetime
        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        msg_id = f"ELIX-{transfer.id}"
        sender_name = f"{transfer.sender_account.user.first_name} {transfer.sender_account.user.last_name}".strip()
        sender_account_iban = f"PL{transfer.sender_account.iban}" if not transfer.sender_account.iban.startswith("PL") else transfer.sender_account.iban
        receiver_account_iban = f"PL{transfer.recipient_iban}" if not transfer.recipient_iban.startswith("PL") else transfer.recipient_iban

        # Generujemy XML ISO 20022
        xml_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document>
    <FIToFICstmrCdtTrf>
        <GrpHdr>
            <MsgId>{msg_id}</MsgId>
            <CreDtTm>{now_iso}</CreDtTm>
            <NbOfTxs>1</NbOfTxs>
            <TtlIntrBkSttlmAmt Ccy="PLN">{transfer.amount}</TtlIntrBkSttlmAmt>
            <SttlmInf>
                <SttlmMtd>CLRG</SttlmMtd>
                <ClrSys><Cd>ELIXIR</Cd></ClrSys>
            </SttlmInf>
        </GrpHdr>
        <CdtTrfTxInf>
            <PmtId>
                <InstrId>{msg_id}</InstrId>
                <EndToEndId>{msg_id}</EndToEndId>
                <TxId>{msg_id}</TxId>
            </PmtId>
            <IntrBkSttlmAmt Ccy="PLN">{transfer.amount}</IntrBkSttlmAmt>
            <Dbtr><Nm>{sender_name}</Nm></Dbtr>
            <DbtrAgt><FinInstnId><BICFI>{sender_bank_id}</BICFI></FinInstnId></DbtrAgt>
            <Cdtr><Nm>{transfer.recipient_name}</Nm></Cdtr>
            <CdtrAgt><FinInstnId><BICFI>{receiver_bank_id}</BICFI></FinInstnId></CdtrAgt>
            <DbtrAcct><Id><IBAN>{sender_account_iban}</IBAN></Id></DbtrAcct>
            <CdtrAcct><Id><IBAN>{receiver_account_iban}</IBAN></Id></CdtrAcct>
            <RmtInf><Ustrd>{transfer.title}</Ustrd></RmtInf>
            <SplmtryData>
                <Envlp>
                    <ServiceCode>ELIXIR</ServiceCode>
                    <SenderBankId>{sender_bank_id}</SenderBankId>
                    <ReceiverBankId>{receiver_bank_id}</ReceiverBankId>
                </Envlp>
            </SplmtryData>
        </CdtTrfTxInf>
    </FIToFICstmrCdtTrf>
</Document>'''

        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml"
        }

        try:
            response = requests.post(ELIXIR_API_URL, data=xml_payload.encode('utf-8'), headers=headers, timeout=5)
            if response.status_code == 200:
                # Otrzymaliśmy <PaymentResponse>
                return True
            else:
                raise APIException(f"Błąd integracji z Elixir: {response.status_code} {response.text}")
        except requests.exceptions.RequestException as e:
            raise APIException(f"Błąd komunikacji z serwerem Elixir: {str(e)}")

EXPRESS_ELIXIR_API_URL = "http://host.docker.internal:8082/api/payments"

class ExpressElixirIntegrationService:
    @staticmethod
    def send_transfer(transfer: Transfer):
        """
        Wysyła przelew do zewnętrznego systemu Express Elixir w formacie JSON.
        """
        sender_bank_id = "BANK_B"
        
        # Wyznaczamy receiverBankId na podstawie prefiksu IBAN
        receiver_iban_prefix = transfer.recipient_iban[:6]
        if receiver_iban_prefix == "111111":
            receiver_bank_id = "BANK_A"
        elif receiver_iban_prefix == "222222":
            receiver_bank_id = "BANK_B"
        elif receiver_iban_prefix == "333333":
            receiver_bank_id = "BANK_C"
        else:
            receiver_bank_id = "BANK_A" # Domyślnie BANK_A dla pozostałych

        sender_name = f"{transfer.sender_account.user.first_name} {transfer.sender_account.user.last_name}".strip()
        sender_account_iban = f"PL{transfer.sender_account.iban}" if not transfer.sender_account.iban.startswith("PL") else transfer.sender_account.iban
        receiver_account_iban = f"PL{transfer.recipient_iban}" if not transfer.recipient_iban.startswith("PL") else transfer.recipient_iban

        # Generujemy JSON
        json_payload = {
            "paymentId": str(transfer.id),
            "amount": float(transfer.amount),
            "currency": "PLN",
            "senderBankId": sender_bank_id,
            "receiverBankId": receiver_bank_id,
            "senderAccount": sender_account_iban,
            "receiverAccount": receiver_account_iban,
            "title": transfer.title,
            "senderName": sender_name,
            "receiverName": transfer.recipient_name,
            "type": "ELIXIR_EXPRESS"
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        try:
            response = requests.post(EXPRESS_ELIXIR_API_URL, json=json_payload, headers=headers, timeout=5)
            if response.status_code == 200:
                return True
            else:
                raise APIException(f"Błąd integracji z Express Elixir: {response.status_code} {response.text}")
        except requests.exceptions.RequestException as e:
            raise APIException(f"Błąd komunikacji z serwerem Express Elixir: {str(e)}")

SORBNET_API_URL = "http://host.docker.internal:8083/api/sorbnet/payments"

import xml.etree.ElementTree as ET
from datetime import datetime

class SorbnetIntegrationService:
    @staticmethod
    def send_transfer(transfer: Transfer):
        """
        Wysyła przelew do zewnętrznego systemu Sorbnet w formacie ISO-20022 (pacs.008).
        """
        sender_bank_id = "BANK_B"
        
        # Wyznaczamy receiverBankId na podstawie prefiksu IBAN
        receiver_iban_prefix = transfer.recipient_iban[:6]
        if receiver_iban_prefix == "111111":
            receiver_bank_id = "BANK_A"
        elif receiver_iban_prefix == "222222":
            receiver_bank_id = "BANK_B"
        elif receiver_iban_prefix == "333333":
            receiver_bank_id = "BANK_C"
        else:
            receiver_bank_id = "BANK_A"

        now_iso = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        msg_id = f"SORB-{transfer.id}"
        
        sender_name = f"{transfer.sender_account.user.first_name} {transfer.sender_account.user.last_name}".strip()

        # Generujemy XML
        xml_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document>
    <FIToFICstmrCdtTrf>
        <GrpHdr>
            <MsgId>{msg_id}</MsgId>
            <CreDtTm>{now_iso}</CreDtTm>
            <NbOfTxs>1</NbOfTxs>
            <TtlIntrBkSttlmAmt Ccy="PLN">{transfer.amount}</TtlIntrBkSttlmAmt>
            <SttlmInf>
                <SttlmMtd>CLRG</SttlmMtd>
                <ClrSys><Cd>SORBNET</Cd></ClrSys>
            </SttlmInf>
        </GrpHdr>
        <CdtTrfTxInf>
            <PmtId>
                <InstrId>{msg_id}</InstrId>
                <EndToEndId>{msg_id}</EndToEndId>
                <TxId>{msg_id}</TxId>
            </PmtId>
            <IntrBkSttlmAmt Ccy="PLN">{transfer.amount}</IntrBkSttlmAmt>
            <Dbtr><Nm>{sender_name}</Nm></Dbtr>
            <DbtrAgt><FinInstnId><BICFI>{sender_bank_id}</BICFI></FinInstnId></DbtrAgt>
            <Cdtr><Nm>{transfer.recipient_name}</Nm></Cdtr>
            <CdtrAgt><FinInstnId><BICFI>{receiver_bank_id}</BICFI></FinInstnId></CdtrAgt>
            <RmtInf><Ustrd>{transfer.title}</Ustrd></RmtInf>
            <SplmtryData>
                <Envlp>
                    <ServiceCode>SORBNET</ServiceCode>
                    <SenderBankId>{sender_bank_id}</SenderBankId>
                    <ReceiverBankId>{receiver_bank_id}</ReceiverBankId>
                </Envlp>
            </SplmtryData>
        </CdtTrfTxInf>
    </FIToFICstmrCdtTrf>
</Document>'''

        headers = {
            "Content-Type": "application/xml",
            "Accept": "application/xml"
        }

        try:
            response = requests.post(SORBNET_API_URL, data=xml_payload.encode('utf-8'), headers=headers, timeout=10)
            if response.status_code == 200:
                try:
                    root = ET.fromstring(response.text)
                    # Szukamy <TxSts> w głębi XML
                    # Elementy ISO zazwyczaj są parsowane z zachowaniem przestrzeni nazw, 
                    # ale jeśli nie zadeklarowano ns, tag to po prostu TxSts
                    tx_sts_elem = root.find(".//TxSts")
                    
                    if tx_sts_elem is not None:
                        status = tx_sts_elem.text
                    else:
                        raise APIException("Brak elementu TxSts w odpowiedzi Sorbnet.")

                    return status
                except ET.ParseError:
                    raise APIException("Błąd parsowania XML z odpowiedzi Sorbnet.")
            else:
                raise APIException(f"Błąd integracji z Sorbnet: {response.status_code} {response.text}")
        except requests.exceptions.RequestException as e:
            raise APIException(f"Błąd komunikacji z serwerem Sorbnet: {str(e)}")

    @staticmethod
    def sync_transfers():
        from accounts.models import Account
        from transfers.models import Transfer
        from django.db import transaction

        pending_transfers = Transfer.objects.filter(
            system_route='SORBNET',
            status='PENDING'
        )
        for transfer in pending_transfers:
            msg_id = f"SORB-{transfer.id}"
            try:
                response = requests.get(f"{SORBNET_API_URL}/{msg_id}", timeout=10)
                if response.status_code == 200:
                    try:
                        root = ET.fromstring(response.text)
                        tx_sts_elem = root.find(".//TxSts")
                        if tx_sts_elem is not None:
                            status = tx_sts_elem.text
                            if status in ['SETTLED', 'REJECTED']:
                                with transaction.atomic():
                                    t = Transfer.objects.select_for_update().get(id=transfer.id)
                                    if t.status != 'PENDING':
                                        continue
                                    acc = Account.objects.select_for_update().get(id=t.sender_account.id)
                                    if status == 'SETTLED':
                                        t.status = 'COMPLETED'
                                        if acc.blocked_funds >= t.amount:
                                            acc.blocked_funds -= t.amount
                                        acc.balance -= t.amount
                                    elif status == 'REJECTED':
                                        t.status = 'FAILED'
                                        if acc.blocked_funds >= t.amount:
                                            acc.blocked_funds -= t.amount
                                    acc.save(update_fields=['balance', 'blocked_funds'])
                                    t.save(update_fields=['status'])
                    except ET.ParseError:
                        pass
            except requests.exceptions.RequestException:
                pass


# ──────────────────────────────────────────────
#  SWIFT (ISO 20022 pacs.008) – przelewy zagraniczne
# ──────────────────────────────────────────────

SWIFT_BASE_URL = getattr(settings, 'SWIFT_BASE_URL', 'http://host.docker.internal:3000')
SWIFT_BIC = "PLBKPL01XXX"            # BIC naszego banku w sieci SWIFT
SWIFT_CLIENT_ID = "bank-plbkpl01"
SWIFT_CLIENT_SECRET = "secret-plbkpl01"

import threading
import time as _time
import requests
import uuid
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from rest_framework.exceptions import APIException

class SwiftIntegrationService:
    """
    Integracja z symulatorem SWIFT Middleware.
    Obsługuje:
      - Pobieranie tokenu OAuth2 (z cache wewnątrz procesu)
      - Wysyłanie przelewu XML ISO 20022 pacs.008
      - Anulowanie przelewu w oknie czasowym (UETR)
    """

    _token: str | None = None
    _token_expiry: float = 0.0
    _lock = threading.Lock()

    @classmethod
    def get_token(cls) -> str:
        with cls._lock:
            if cls._token and _time.time() < cls._token_expiry:
                return cls._token

            try:
                resp = requests.post(
                    f"{SWIFT_BASE_URL}/auth/token",
                    data={
                        "client_id": SWIFT_CLIENT_ID,
                        "client_secret": SWIFT_CLIENT_SECRET,
                        "grant_type": "client_credentials",
                    },
                    timeout=10,
                )
                if resp.status_code != 200:
                    raise APIException(f"SWIFT OAuth2 error: {resp.status_code} {resp.text}")

                data = resp.json()
                cls._token = data["access_token"]
                cls._token_expiry = _time.time() + data.get("expires_in", 3600) - 300
                return cls._token

            except requests.exceptions.RequestException as e:
                raise APIException(f"Błąd komunikacji z SWIFT (token): {str(e)}")

    @classmethod
    def send_transfer(cls, transfer) -> str:
        uetr = str(uuid.uuid4())

        sender_name = (
            f"{transfer.sender_account.user.first_name} "
            f"{transfer.sender_account.user.last_name}"
        ).strip()

        sender_iban = transfer.sender_account.iban
        if not sender_iban.startswith("PL"):
            sender_iban = f"PL{sender_iban}"

        recipient_iban = transfer.recipient_iban

        def _bic_for_iban(iban: str) -> str:
            iban = iban.upper()
            if iban.startswith("GB"):
                return "UKBKGB01XXX"
            elif iban.startswith("US"):
                return "USBKUS01XXX"
            elif iban.startswith("DE"):
                return "DEBKDE01XXX"
            elif iban.startswith("FR"):
                return "EUBKFR01XXX"
            elif iban.startswith("PL22"):
                return "PLBKPL02XXX"
            else:
                return "PLBKPL01XXX"

        receiver_bic = _bic_for_iban(recipient_iban)

        def _currency_and_rate_for_iban(iban: str) -> tuple[str, Decimal]:
            iban = iban.upper()
            if iban.startswith("GB"):
                return "GBP", Decimal('5.00')
            elif iban.startswith("US"):
                return "USD", Decimal('4.00')
            elif iban.startswith("DE") or iban.startswith("FR"):
                return "EUR", Decimal('4.30')
            else:
                return "PLN", Decimal('1.00')

        currency, exchange_rate = _currency_and_rate_for_iban(recipient_iban)
        
        amount_decimal = transfer.amount if isinstance(transfer.amount, Decimal) else Decimal(str(transfer.amount))
        converted_amount = (amount_decimal / exchange_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        charge_bearer = transfer.swift_charge_bearer or "SHA"

        now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        settle_date = datetime.utcnow().strftime("%Y-%m-%d")
        msg_id = f"SWIFT-{str(transfer.id)[:18]}"

        xml_payload = f'''<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08">
  <FIToFICstmrCdtTrf>
    <GrpHdr>
      <MsgId>{msg_id}</MsgId>
      <CreDtTm>{now_iso}</CreDtTm>
      <NbOfTxs>1</NbOfTxs>
      <SttlmInf><SttlmMtd>INDA</SttlmMtd></SttlmInf>
    </GrpHdr>
    <CdtTrfTxInf>
      <PmtId>
        <InstrId>{msg_id}</InstrId>
        <EndToEndId>{msg_id}</EndToEndId>
        <UETR>{uetr}</UETR>
      </PmtId>
      <IntrBkSttlmAmt Ccy="{currency}">{converted_amount}</IntrBkSttlmAmt>
      <IntrBkSttlmDt>{settle_date}</IntrBkSttlmDt>
      <InstdAmt Ccy="{currency}">{converted_amount}</InstdAmt>
      <ChrgBr>{charge_bearer}</ChrgBr>
      <DbtrAgt><FinInstnId><BICFI>{SWIFT_BIC}</BICFI></FinInstnId></DbtrAgt>
      <Dbtr><Nm>{sender_name}</Nm></Dbtr>
      <DbtrAcct><Id><IBAN>{sender_iban}</IBAN></Id></DbtrAcct>
      <CdtrAgt><FinInstnId><BICFI>{receiver_bic}</BICFI></FinInstnId></CdtrAgt>
      <Cdtr><Nm>{transfer.recipient_name}</Nm></Cdtr>
      <CdtrAcct><Id><Othr><Id>{recipient_iban}</Id></Othr></Id></CdtrAcct>
      <RmtInf><Ustrd>{transfer.title}</Ustrd></RmtInf>
    </CdtTrfTxInf>
  </FIToFICstmrCdtTrf>
</Document>'''

        token = cls.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/xml",
            "X-SWIFT-Callback-Url": getattr(settings, 'BACKEND_URL', 'http://host.docker.internal:8080') + "/api/swift/ack",
            "X-SWIFT-Return-Url": getattr(settings, 'BACKEND_URL', 'http://host.docker.internal:8080') + "/api/swift/return"
        }

        try:
            resp = requests.post(
                f"{SWIFT_BASE_URL}/swift/message",
                data=xml_payload.encode("utf-8"),
                headers=headers,
                timeout=15,
            )
            if resp.status_code == 202:
                return uetr
            else:
                raise APIException(f"SWIFT odrzucił przelew: {resp.status_code} {resp.text}")
        except requests.exceptions.RequestException as e:
            raise APIException(f"Błąd komunikacji z SWIFT: {str(e)}")

    @classmethod
    def cancel_transfer(cls, uetr: str) -> bool:
        token = cls.get_token()
        try:
            resp = requests.post(
                f"{SWIFT_BASE_URL}/swift/cancel/{uetr}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.exceptions.RequestException:
            return False
