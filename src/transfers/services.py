import requests
import uuid
from decimal import Decimal
from django.conf import settings
from rest_framework.exceptions import APIException
from .models import Transfer

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

