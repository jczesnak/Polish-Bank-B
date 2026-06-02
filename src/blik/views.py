import re
from decimal import Decimal

from django.db import transaction as db_transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from transfers.models import ApprovalRequest, Transfer
from transfers.notifications import send_user_event
from .models import BlikCode, BlikTransaction, PhoneAlias, P2pContact
from .serializers import (
    BlikGenerateSerializer,
    BlikWebhookSerializer,
    BlikPingSerializer,
    BlikTransactionSerializer,
    PhoneAliasSerializer,
    RegisterAliasSerializer,
    P2PTransferSerializer,
    P2pContactSerializer,
)
from .services import KlikService, KlikError
from .payments import accept_blik_transaction, reject_blik_transaction, BlikPaymentError


def normalize_phone(raw: str) -> str:
    """Doprowadza numer do formatu E.164 dla strefy PL.

    Akceptuje '+48501234567', '48501234567' oraz krajowe '501234567'.
    """
    phone = re.sub(r'[\s-]', '', (raw or '').strip())
    if phone.startswith('+'):
        return phone
    if phone.startswith('48') and len(phone) == 11:
        return f'+{phone}'
    if len(phone) == 9 and phone.isdigit():
        return f'+48{phone}'
    return phone


class BlikGenerateView(APIView):
    """Generuje 6-cyfrowy kod BLIK dla zalogowanego klienta."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BlikGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        account_id = serializer.validated_data['account_id']
        try:
            account = Account.objects.get(pk=account_id, user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = KlikService().generate_code(user_id=str(request.user.id))
        except KlikError as exc:
            return Response(
                {'detail': f'Błąd komunikacji z systemem KLIK: {exc.message}', 'code': exc.code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        BlikCode.objects.create(
            user=request.user,
            account=account,
            code=result['code'],
            expires_at=parse_datetime(result['expires_at']),
        )

        return Response({
            'code': result['code'],
            'expires_at': result['expires_at'],
            'expires_in': result.get('expires_in', 120),
        })


class BlikWebhookAuthorizeView(APIView):
    """
    Webhook wywoływany przez KLIK gdy merchant inicjuje płatność kodem.

    KLIK nie przekazuje user_id ani kodu — korelujemy transakcję z najstarszym
    aktywnym kodem BLIK (FIFO), analogicznie do referencyjnego bank_IO.
    Bank sprawdza środki, zakłada blokadę i wywołuje /payments/confirm do KLIK.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BlikWebhookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        blik_code = self._match_code(data.get('user_id'))
        if blik_code is None:
            return Response({'detail': 'Brak aktywnego kodu BLIK.'}, status=status.HTTP_404_NOT_FOUND)

        amount = Decimal(str(data['amount']))

        with db_transaction.atomic():
            account = Account.objects.select_for_update().get(pk=blik_code.account_id)

            if account.available_balance < amount:
                self._finalize_code(blik_code)
                BlikTransaction.objects.create(
                    klik_transaction_id=data['transaction_id'],
                    account=account,
                    user=blik_code.user,
                    amount=amount,
                    currency=data['currency'],
                    merchant_name=data.get('merchant_name', ''),
                    status=BlikTransaction.Status.REJECTED,
                    reject_reason=BlikTransaction.RejectReason.INSUFFICIENT_FUNDS,
                    completed_at=timezone.now(),
                )
                self._safe_reject(data['transaction_id'], 'INSUFFICIENT_FUNDS')
                return Response({'received': True, 'will_prompt_user': False})

            account.blocked_funds += amount
            account.save(update_fields=['blocked_funds'])

            if account.account_type == Account.AccountType.JUNIOR:
                if not account.parent_account_id:
                    account.blocked_funds -= amount
                    account.save(update_fields=['blocked_funds'])
                    self._finalize_code(blik_code)
                    self._safe_reject(data['transaction_id'], 'OTHER')
                    return Response(
                        {'detail': 'Konto Junior nie ma przypisanego konta rodzica.'},
                        status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    )

                transaction = BlikTransaction.objects.create(
                    klik_transaction_id=data['transaction_id'],
                    account=account,
                    user=blik_code.user,
                    amount=amount,
                    currency=data['currency'],
                    merchant_name=data.get('merchant_name', ''),
                    status=BlikTransaction.Status.PENDING,
                )
                self._finalize_code(blik_code)

                parent = account.parent_account.user
                approval = ApprovalRequest.objects.create(
                    request_type=ApprovalRequest.RequestType.BLIK_PAYMENT,
                    junior=blik_code.user,
                    parent=parent,
                    account=account,
                    blik_transaction=transaction,
                )

            else:
                transaction = BlikTransaction.objects.create(
                    klik_transaction_id=data['transaction_id'],
                    account=account,
                    user=blik_code.user,
                    amount=amount,
                    currency=data['currency'],
                    merchant_name=data.get('merchant_name', ''),
                    status=BlikTransaction.Status.PENDING,
                )
                self._finalize_code(blik_code)
                approval = None

        if account.account_type == Account.AccountType.JUNIOR:
            send_user_event(parent.id, 'approval.created', {
                'approval_id': str(approval.id),
                'type': approval.request_type,
                'junior_name': f'{blik_code.user.first_name} {blik_code.user.last_name}'.strip(),
                'amount': str(amount),
                'target': data.get('merchant_name') or 'Płatność BLIK',
            })
            return Response({'received': True, 'will_prompt_user': True})

        send_user_event(blik_code.user_id, 'blik.pending', {
            'transaction_id': str(transaction.id),
            'amount': str(amount),
            'merchant_name': data.get('merchant_name') or 'Płatność BLIK',
        })
        return Response({'received': True, 'will_prompt_user': True})

    @staticmethod
    def _match_code(user_id):
        qs = BlikCode.objects.filter(
            status=BlikCode.Status.ACTIVE,
            expires_at__gt=timezone.now(),
        )
        if user_id:
            qs = qs.filter(user__id=user_id)
        return qs.order_by('created_at').first()

    @staticmethod
    def _finalize_code(blik_code):
        blik_code.status = BlikCode.Status.USED
        blik_code.save(update_fields=['status'])

    @staticmethod
    def _safe_reject(transaction_id, reason):
        try:
            KlikService().confirm_payment(
                transaction_id=str(transaction_id),
                decision='REJECTED',
                reject_reason=reason,
            )
        except KlikError:
            pass


class BlikPingView(APIView):
    """Healthcheck wywoływany przez KLIK przy rejestracji webhooka."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = BlikPingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response({
            'timestamp': serializer.validated_data['timestamp'],
            'nonce': serializer.validated_data['nonce'],
            'pong': True,
        })


class BlikTransactionListView(generics.ListAPIView):
    serializer_class = BlikTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BlikTransaction.objects.filter(user=self.request.user)


class BlikPendingListView(generics.ListAPIView):
    """Oczekujące autoryzacje BLIK zalogowanego klienta (konto dorosłe)."""
    serializer_class = BlikTransactionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return BlikTransaction.objects.filter(
            user=self.request.user,
            status=BlikTransaction.Status.PENDING,
        )


class BlikAuthorizationDecisionView(APIView):
    """Akceptacja lub odrzucenie oczekującej płatności BLIK przez klienta."""
    permission_classes = [IsAuthenticated]

    @db_transaction.atomic
    def post(self, request, pk, decision):
        try:
            blik_tx = BlikTransaction.objects.select_for_update().get(
                pk=pk, user=request.user, status=BlikTransaction.Status.PENDING,
            )
        except BlikTransaction.DoesNotExist:
            return Response({'detail': 'Autoryzacja BLIK nie istnieje lub wygasła.'}, status=status.HTTP_404_NOT_FOUND)

        if blik_tx.account.account_type == Account.AccountType.JUNIOR:
            return Response(
                {'detail': 'Płatność BLIK konta Junior wymaga zgody rodzica.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            if decision == 'reject':
                reject_blik_transaction(blik_tx)
            else:
                accept_blik_transaction(blik_tx)
        except BlikPaymentError as exc:
            return Response({'detail': exc.message}, status=exc.http_status)

        return Response(BlikTransactionSerializer(blik_tx).data)


# --- P2P (przelew na telefon) --------------------------------------------

EXPRESS_ELIXIR_MAX = Decimal('100000.00')


class P2PAliasView(APIView):
    """Zarządzanie własnymi aliasami P2P (telefon → konto) klienta."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        aliases = PhoneAlias.objects.filter(user=request.user)
        return Response(PhoneAliasSerializer(aliases, many=True).data)

    def post(self, request):
        serializer = RegisterAliasSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            account = Account.objects.get(pk=data['account_id'], user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        raw_phone = data.get('phone') or request.user.phone_number
        phone = normalize_phone(raw_phone)
        if not phone.startswith('+'):
            return Response(
                {'phone': 'Podaj numer telefonu w formacie E.164 (np. +48501234567) lub uzupełnij profil.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if PhoneAlias.objects.filter(phone=phone).exists():
            return Response(
                {'detail': 'Ten numer jest już zarejestrowany jako alias P2P w tym banku.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            result = KlikService().register_alias(phone=phone, iban=account.iban, zone='PL')
        except KlikError as exc:
            http = status.HTTP_409_CONFLICT if exc.status_code == 409 else status.HTTP_502_BAD_GATEWAY
            return Response(
                {'detail': f'KLIK odrzucił rejestrację aliasu: {exc.message}', 'code': exc.code},
                status=http,
            )

        alias = PhoneAlias.objects.create(
            user=request.user,
            account=account,
            phone=phone,
            klik_alias_id=result.get('alias_id'),
            zone='PL',
        )
        return Response(PhoneAliasSerializer(alias).data, status=status.HTTP_201_CREATED)


class P2PAliasDeleteView(APIView):
    """Wyrejestrowanie aliasu P2P (z KLIK i z lokalnego rejestru)."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, phone):
        phone = normalize_phone(phone)
        try:
            alias = PhoneAlias.objects.get(phone=phone, user=request.user)
        except PhoneAlias.DoesNotExist:
            return Response({'detail': 'Alias nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            KlikService().delete_alias(phone)
        except KlikError as exc:
            # 404 po stronie KLIK = już go nie ma — usuwamy lokalnie i tak.
            if exc.status_code != 404:
                return Response(
                    {'detail': f'KLIK odrzucił usunięcie aliasu: {exc.message}', 'code': exc.code},
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        alias.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class P2PLookupView(APIView):
    """Sprawdzenie czy numer telefonu jest zarejestrowany w KLIK (routing)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, phone):
        phone = normalize_phone(phone)
        try:
            result = KlikService().lookup_alias(phone)
        except KlikError as exc:
            if exc.status_code == 404:
                return Response({'found': False, 'phone': phone})
            return Response(
                {'detail': f'Błąd lookupu w KLIK: {exc.message}', 'code': exc.code},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({'found': True, **result})


class P2PTransferView(APIView):
    """Przelew na telefon: lookup w KLIK → realizacja przelewu (Express Elixir).

    KLIK zwraca tylko routing (IBAN odbiorcy + bank). Sam transfer środków bank
    realizuje poza KLIK — zgodnie z domeną BLIK P2P przez Express Elixir
    (rozrachunek na koncie pre-funded). Jeśli odbiorca jest w naszym banku,
    księgujemy wewnętrznie natychmiast.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = P2PTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        phone = normalize_phone(data['recipient_phone'])
        amount = data['amount']
        recipient_name = (data.get('recipient_name') or '').strip()

        if amount > EXPRESS_ELIXIR_MAX:
            return Response(
                {'amount': f'Przelew na telefon (Express Elixir) ma limit {EXPRESS_ELIXIR_MAX} PLN.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            sender = Account.objects.get(pk=data['sender_account'], user=request.user)
        except Account.DoesNotExist:
            return Response({'detail': 'Rachunek nadawcy nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)

        # 1) Routing przez KLIK
        try:
            routing = KlikService().lookup_alias(phone)
        except KlikError as exc:
            if exc.status_code == 404:
                return Response(
                    {'detail': 'Numer telefonu nie jest zarejestrowany w KLIK. Użyj przelewu na IBAN.',
                     'code': 'ALIAS_NOT_FOUND'},
                    status=status.HTTP_404_NOT_FOUND,
                )
            return Response(
                {'detail': f'Błąd lookupu w KLIK: {exc.message}', 'code': exc.code},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        recipient_iban = routing.get('iban')
        if not recipient_iban:
            return Response(
                {'detail': 'KLIK nie zwrócił IBAN odbiorcy (strefa spoza PL/EU/UK?).'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        display_name = recipient_name or phone
        is_junior = sender.account_type == Account.AccountType.JUNIOR

        if is_junior:
            with db_transaction.atomic():
                sender = Account.objects.select_for_update().get(pk=sender.id)
                if sender.available_balance < amount:
                    return Response(
                        {'amount': 'Niewystarczające środki na rachunku.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                transfer = Transfer.objects.create(
                    sender_account=sender,
                    recipient_iban=recipient_iban,
                    recipient_name=display_name,
                    amount=amount,
                    title=data['title'],
                    system_route=Transfer.TransferSystem.KLIK,
                    status=Transfer.Status.PENDING_APPROVAL,
                    processed_at=None,
                )
                parent = sender.parent_account.user
                approval = ApprovalRequest.objects.create(
                    request_type=ApprovalRequest.RequestType.TRANSFER,
                    junior=request.user,
                    parent=parent,
                    account=sender,
                    transfer=transfer,
                )

            send_user_event(parent.id, 'approval.created', {
                'approval_id': str(approval.id),
                'type': approval.request_type,
                'junior_name': f'{request.user.first_name} {request.user.last_name}'.strip(),
                'amount': str(transfer.amount),
                'target': f'{display_name} ({phone})',
            })

            saved_contact = False
            if data.get('save_contact') and recipient_name:
                _, created = P2pContact.objects.update_or_create(
                    user=request.user,
                    phone=phone,
                    defaults={'name': recipient_name},
                )
                saved_contact = created

            return Response({
                'message': 'Przelew na telefon oczekuje na zgodę rodzica.',
                'transfer_id': transfer.id,
                'approval_id': approval.id,
                'recipient_phone': phone,
                'recipient_name': display_name,
                'recipient_iban': recipient_iban,
                'recipient_bank': routing.get('bank_code'),
                'amount': str(amount),
                'system_route': Transfer.TransferSystem.KLIK,
                'status': transfer.status,
                'contact_saved': saved_contact,
            }, status=status.HTTP_202_ACCEPTED)

        # 2) Realizacja przelewu po stronie banku (konto dorosłego)
        with db_transaction.atomic():
            sender = Account.objects.select_for_update().get(pk=sender.id)
            if sender.available_balance < amount:
                return Response({'amount': 'Niewystarczające środki na rachunku.'},
                                status=status.HTTP_400_BAD_REQUEST)

            recipient_account = Account.objects.select_for_update().filter(iban=recipient_iban).first()

            sender.balance -= amount
            if recipient_account is not None:
                recipient_account.balance += amount
                recipient_account.save(update_fields=['balance'])
            # Przelew na telefon zawsze idzie przez KLIK – tak go oznaczamy,
            # niezależnie od tego czy odbiorca jest w naszym banku (księgowanie
            # wewnętrzne) czy poza nim (Express Elixir).
            route = Transfer.TransferSystem.KLIK
            sender.save(update_fields=['balance'])

            # Nazwa odbiorcy do historii: podane imię i nazwisko, a w razie
            # braku – numer telefonu (czytelniejszy niż kod banku z KLIK).
            display_name = recipient_name or phone
            transfer = Transfer.objects.create(
                sender_account=sender,
                recipient_iban=recipient_iban,
                recipient_name=display_name,
                amount=amount,
                title=data['title'],
                system_route=route,
                status=Transfer.Status.COMPLETED,
                processed_at=timezone.now(),
            )

        # Opcjonalny zapis kontaktu (poza transakcją księgową – nie blokuje przelewu).
        saved_contact = False
        if data.get('save_contact') and recipient_name:
            _, created = P2pContact.objects.update_or_create(
                user=request.user,
                phone=phone,
                defaults={'name': recipient_name},
            )
            saved_contact = True

        return Response({
            'message': 'Przelew na telefon zrealizowany.',
            'transfer_id': transfer.id,
            'recipient_phone': phone,
            'recipient_name': display_name,
            'recipient_iban': recipient_iban,
            'recipient_bank': routing.get('bank_code'),
            'amount': str(amount),
            'system_route': route,
            'status': transfer.status,
            'contact_saved': saved_contact,
        }, status=status.HTTP_201_CREATED)


class P2PContactView(APIView):
    """Kontakty P2P klienta: lista (GET) i dodanie/aktualizacja (POST)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        contacts = P2pContact.objects.filter(user=request.user)
        return Response(P2pContactSerializer(contacts, many=True).data)

    def post(self, request):
        serializer = P2pContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone = normalize_phone(serializer.validated_data['phone'])
        contact, _ = P2pContact.objects.update_or_create(
            user=request.user,
            phone=phone,
            defaults={'name': serializer.validated_data['name']},
        )
        return Response(P2pContactSerializer(contact).data, status=status.HTTP_201_CREATED)


class P2PContactDeleteView(APIView):
    """Usunięcie kontaktu P2P."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, contact_id):
        try:
            contact = P2pContact.objects.get(pk=contact_id, user=request.user)
        except P2pContact.DoesNotExist:
            return Response({'detail': 'Kontakt nie istnieje.'}, status=status.HTTP_404_NOT_FOUND)
        contact.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
