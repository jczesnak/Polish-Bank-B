# src/transfers/views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.db import transaction
import xml.etree.ElementTree as ET

from .models import Transfer

from .serializers import TransferSerializer, InternalTransferSerializer, CreateTransferSerializer
from accounts.models import Account
from .services import ElixirIntegrationService


class IncomingTransferListView(generics.ListAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user_ibans = Account.objects.filter(user=self.request.user).values_list('iban', flat=True)
        return Transfer.objects.filter(recipient_iban__in=user_ibans).order_by('-created_at')


class TransferAMLExplainView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        try:
            transfer = Transfer.objects.select_for_update().get(id=pk, sender_account__user=request.user, status='AML_SUSPENDED')
        except Transfer.DoesNotExist:
            return Response({'error': 'Nie znaleziono zablokowanego przelewu.'}, status=status.HTTP_404_NOT_FOUND)

        explanation = request.data.get('explanation', '').strip()
        if not explanation:
            return Response({'error': 'Wymagane jest podanie wyjaśnienia.'}, status=status.HTTP_400_BAD_REQUEST)

        transfer.aml_explanation = explanation
        transfer.save(update_fields=['aml_explanation'])
        
        return Response({'status': 'W_WERYFIKACJI', 'message': 'Wyjaśnienie zostało wysłane do ręcznej weryfikacji przez pracownika banku.'}, status=status.HTTP_200_OK)

class TransferListCreateView(generics.ListCreateAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreateTransferSerializer
        return TransferSerializer

    def get_queryset(self):
        try:
            from .services import SorbnetIntegrationService
            SorbnetIntegrationService.sync_transfers()
        except Exception:
            pass
        return Transfer.objects.filter(sender_account__user=self.request.user)
        
    @transaction.atomic
    def perform_create(self, serializer):
        transfer = serializer.save(status='PENDING')
        
        from .services import check_aml
        if not check_aml(transfer):
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save(update_fields=['blocked_funds'])
            return

        
        # Jeśli przelew idzie systemem ELIXIR, blokujemy środki i wysyłamy do Elixira
        if transfer.system_route == 'ELIXIR':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save()
            
            try:
                ElixirIntegrationService.send_transfer(transfer)
            except Exception as e:
                raise e
        # Jeśli przelew idzie systemem EXPRESS_ELIXIR, blokujemy środki i wysyłamy do Express Elixira
        elif transfer.system_route == 'EXPRESS_ELIXIR':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save()
            
            try:
                from .services import ExpressElixirIntegrationService
                ExpressElixirIntegrationService.send_transfer(transfer)
            except Exception as e:
                raise e
        elif transfer.system_route == 'SORBNET':
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            
            try:
                from .services import SorbnetIntegrationService
                sorbnet_status = SorbnetIntegrationService.send_transfer(transfer)
                
                if sorbnet_status == 'SETTLED':
                    transfer.status = 'COMPLETED'
                    transfer.save()
                    account.balance -= transfer.amount
                    account.save()
                elif sorbnet_status == 'REJECTED':
                    transfer.status = 'FAILED'
                    transfer.save()
                elif sorbnet_status == 'GRIDLOCK_HELD':
                    account.blocked_funds += transfer.amount
                    account.save()
            except Exception as e:
                raise e

        elif transfer.system_route == 'SWIFT':
            # Blokujemy środki – zostaną zdjęte po callbacku ACK
            account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
            account.blocked_funds += transfer.amount
            account.save()

            try:
                from .services import SwiftIntegrationService
                # Pobieramy charge_bearer z danych żądania (domyślnie SHA)
                charge_bearer = serializer.validated_data.get('swift_charge_bearer', 'SHA')
                transfer.swift_charge_bearer = charge_bearer
                transfer.save(update_fields=['swift_charge_bearer'])

                uetr = SwiftIntegrationService.send_transfer(transfer)
                transfer.swift_uetr = uetr
                transfer.save(update_fields=['swift_uetr'])
            except Exception as e:
                raise e


class TransferDetailView(generics.RetrieveAPIView):
    serializer_class = TransferSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Transfer.objects.filter(sender_account__user=self.request.user)

class InternalTransferView(APIView):
    permission_classes = [IsAuthenticated]
    
    @transaction.atomic
    def post(self, request):
        serializer = InternalTransferSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        sender_account = data['sender_account']
        recipient_iban = data['recipient_iban']
        amount = data['amount']

        try:

            sender = Account.objects.select_for_update().get(id=sender_account.id)
            receiver = Account.objects.select_for_update().get(iban=recipient_iban)
        except Account.DoesNotExist:
            return Response(
                {"recipient_iban": "Nie znaleziono rachunku odbiorcy w naszym banku. Użyj przelewu zewnętrznego."}, 
                status=status.HTTP_404_NOT_FOUND
            )

        if sender.id == receiver.id:
            return Response(
                {"error": "Nie można wykonać przelewu na ten sam rachunek."}, 
                status=status.HTTP_400_BAD_REQUEST
            )


        transfer = Transfer.objects.create(
            sender_account=sender,
            recipient_iban=recipient_iban,
            recipient_name=data.get('recipient_name', ''),
            amount=amount,
            title=data.get('title', ''),
            system_route='INTERNAL',
            status='PENDING'
        )

        from .services import check_aml
        if not check_aml(transfer):
            sender.blocked_funds += amount
            sender.save(update_fields=['blocked_funds'])
            return Response(TransferSerializer(transfer).data, status=status.HTTP_201_CREATED)

        transfer.status = 'COMPLETED'
        transfer.save(update_fields=['status'])

        sender.balance -= amount
        receiver.balance += amount

        sender.save(update_fields=['balance'])
        receiver.save(update_fields=['balance'])

        return Response(
            {
                "message": "Przelew wewnętrzny został zrealizowany natychmiastowo.", 
                "transfer_id": transfer.id,
                "status": transfer.status,
                "amount": transfer.amount
            },
            status=status.HTTP_201_CREATED
        )


# ─────────────────────────────────────────────────────────
#  SWIFT – Widoki dla przelewów przychodzących i callbacków
# ─────────────────────────────────────────────────────────

NS = "urn:iso:std:iso:20022:tech:xsd:pacs.008.001.08"

def _xml_text(root, *tags):
    """Pomocnik: szuka elementu po tagach (z namespace lub bez)."""
    for tag in tags:
        # próbuj z namespace
        el = root.find(f".//{{{NS}}}{tag}")
        if el is not None and el.text:
            return el.text.strip()
        # próbuj bez namespace (fallback)
        el = root.find(f".//{tag}")
        if el is not None and el.text:
            return el.text.strip()
    return None


class SwiftReceiveView(APIView):
    """
    POST /api/swift/receive
    Odbiera przelew przychodzący od symulatora SWIFT (mock-bank forward).
    Symulator wysyła surowy XML ISO 20022. Parsujemy go i uznajemy konto odbiorcy.
    """
    permission_classes = [AllowAny]  # Symulator nie wysyła tokena przy forwardzie

    @transaction.atomic
    def post(self, request):
        # Symulator może wysłać X-SWIFT-Message-Type: RETURN – obsługujemy osobno
        msg_type = request.headers.get('X-SWIFT-Message-Type', '')
        if msg_type == 'RETURN':
            return self._handle_return(request)

        body = request.body
        if not body:
            return Response({'error': 'Brak ciała żądania'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return Response({'error': 'Nieprawidłowy XML'}, status=status.HTTP_400_BAD_REQUEST)

        uetr = _xml_text(root, 'UETR')
        recipient_iban_raw = _xml_text(root, 'CdtrAcct', 'Id', 'IBAN') or _xml_text(root, 'Id')
        amount_raw = _xml_text(root, 'InstdAmt') or _xml_text(root, 'IntrBkSttlmAmt')
        sender_name = _xml_text(root, 'Dbtr', 'Nm') or 'SWIFT nadawca'
        sender_iban = _xml_text(root, 'DbtrAcct', 'Id', 'IBAN') or ''
        title = _xml_text(root, 'RmtInf', 'Ustrd') or 'Przelew SWIFT'

        # Obsługa konta w CdtrAcct/Id/Othr/Id (format w symulatorze)
        if not recipient_iban_raw:
            othr_el = root.find(f".//{{{NS}}}CdtrAcct//{{{NS}}}Id/{{{NS}}}Othr/{{{NS}}}Id")
            if othr_el is None:
                othr_el = root.find(".//CdtrAcct//Id/Othr/Id")
            if othr_el is not None:
                recipient_iban_raw = othr_el.text.strip() if othr_el.text else None

        if not recipient_iban_raw or not amount_raw:
            return Response(
                {'error': 'Brak konta odbiorcy lub kwoty w XML'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Normalizujemy IBAN – usuwamy prefix PL jeśli jest już w bazie bez niego
        recipient_iban = recipient_iban_raw.upper()
        try:
            from decimal import Decimal
            amount = Decimal(str(amount_raw))
        except Exception:
            return Response({'error': 'Nieprawidłowa kwota'}, status=status.HTTP_400_BAD_REQUEST)

        # Szukamy konta w naszym banku (z PL lub bez)
        account = (
            Account.objects.filter(iban=recipient_iban).first() or
            Account.objects.filter(iban=recipient_iban.replace('PL', '', 1)).first()
        )
        if not account:
            return Response(
                {'error': f'Konto {recipient_iban} nie istnieje w naszym banku'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Uznajemy konto odbiorcy
        account = Account.objects.select_for_update().get(pk=account.pk)
        account.balance += amount
        account.save(update_fields=['balance'])

        transfer = Transfer.objects.create(
            sender_account=account,  # incoming – brak konta nadawcy w naszym banku, używamy konta odbiorcy jako referencji
            recipient_iban=account.iban,
            recipient_name=f"{account.user.first_name} {account.user.last_name}".strip(),
            amount=amount,
            title=title,
            system_route='SWIFT',
            status='COMPLETED',
            swift_uetr=uetr,
        )

        return Response(
            {'status': 'accepted', 'uetr': uetr, 'transfer_id': str(transfer.id)},
            status=status.HTTP_202_ACCEPTED
        )

    def _handle_return(self, request):
        """Obsługa zwrotu przelewu SWIFT (bank odbiorcy odrzucił przelew)."""
        body = request.body
        try:
            root = ET.fromstring(body) if body else None
        except ET.ParseError:
            root = None

        uetr = None
        if root is not None:
            uetr = _xml_text(root, 'UETR')

        if uetr:
            # Szukamy oryginalnego przelewu wychodzącego
            try:
                import uuid as _uuid
                transfer = Transfer.objects.select_for_update().get(
                    swift_uetr=_uuid.UUID(uetr),
                    system_route='SWIFT',
                )
                if transfer.status == 'PENDING':
                    # Zwracamy zablokowane środki
                    account = Account.objects.select_for_update().get(pk=transfer.sender_account.pk)
                    if account.blocked_funds >= transfer.amount:
                        account.blocked_funds -= transfer.amount
                    else:
                        account.blocked_funds = 0
                    account.save(update_fields=['blocked_funds'])
                    transfer.status = 'FAILED'
                    transfer.save(update_fields=['status'])
            except (Transfer.DoesNotExist, Exception):
                pass  # Logujemy w produkcji; symulator nie wymaga błędu

        return Response({'status': 'return_received', 'uetr': uetr}, status=status.HTTP_200_OK)


class SwiftAckView(APIView):
    """
    POST /api/swift/ack
    Callback od symulatora potwierdzający dostarczenie przelewu do banku odbiorcy.
    Body JSON: {"uetr": "...", "status": "accepted", ...}
    Ustawiamy status przelewu na COMPLETED i ściągamy środki z salda.
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        import uuid as _uuid
        uetr_str = request.data.get('uetr')
        if not uetr_str:
            return Response({'error': 'Brak UETR'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uetr = _uuid.UUID(uetr_str)
        except ValueError:
            return Response({'error': 'Nieprawidłowy format UETR'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transfer = Transfer.objects.select_for_update().get(
                swift_uetr=uetr,
                system_route='SWIFT',
            )
        except Transfer.DoesNotExist:
            return Response({'error': 'Przelew SWIFT nie znaleziony'}, status=status.HTTP_404_NOT_FOUND)

        if transfer.status != 'PENDING':
            return Response({'status': 'already_processed'}, status=status.HTTP_200_OK)

        # Ściągamy środki z salda i zdejmujemy blokadę
        account = Account.objects.select_for_update().get(pk=transfer.sender_account.pk)
        if account.blocked_funds >= transfer.amount:
            account.blocked_funds -= transfer.amount
        else:
            account.blocked_funds = 0
        account.balance -= transfer.amount
        account.save(update_fields=['balance', 'blocked_funds'])

        transfer.status = 'COMPLETED'
        transfer.save(update_fields=['status'])

        return Response({'status': 'ok', 'uetr': uetr_str}, status=status.HTTP_200_OK)


class SwiftReturnView(APIView):
    """
    POST /api/swift/return
    Obsługa zwrotu SWIFT (bank odbiorcy → middleware → nasz bank).
    Może przyjść jako JSON lub XML z nagłówkiem X-SWIFT-Message-Type: RETURN.
    """
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        import uuid as _uuid
        # Próbujemy odczytać UETR z JSON lub z nagłówka
        uetr_str = request.data.get('uetr') if isinstance(request.data, dict) else None

        # Jeśli nie ma w JSON, próbujemy sparsować XML
        if not uetr_str:
            try:
                root = ET.fromstring(request.body)
                uetr_str = _xml_text(root, 'UETR')
            except Exception:
                pass

        if not uetr_str:
            return Response({'error': 'Brak UETR w żądaniu'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            uetr = _uuid.UUID(uetr_str)
        except ValueError:
            return Response({'error': 'Nieprawidłowy format UETR'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transfer = Transfer.objects.select_for_update().get(
                swift_uetr=uetr, system_route='SWIFT'
            )
        except Transfer.DoesNotExist:
            return Response({'status': 'not_found'}, status=status.HTTP_200_OK)

        if transfer.status == 'PENDING':
            account = Account.objects.select_for_update().get(pk=transfer.sender_account.pk)
            if account.blocked_funds >= transfer.amount:
                account.blocked_funds -= transfer.amount
            else:
                account.blocked_funds = 0
            account.save(update_fields=['blocked_funds'])
            transfer.status = 'FAILED'
            transfer.save(update_fields=['status'])

        return Response({'status': 'return_received', 'uetr': uetr_str}, status=status.HTTP_200_OK)