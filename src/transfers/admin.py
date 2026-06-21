from django.contrib import admin, messages
from django.db import transaction
from accounts.models import Account
from .models import Transfer

@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender_account', 'recipient_iban', 'amount', 'system_route', 'status', 'created_at', 'aml_explanation')
    list_filter = ('system_route', 'status')
    search_fields = ('recipient_iban', 'recipient_name', 'title')
    readonly_fields = ('id', 'created_at', 'processed_at')
    actions = ['approve_aml', 'reject_aml']

    @admin.action(description='ZAAKCEPTUJ Wyjaśnienie AML i wyślij przelew')
    def approve_aml(self, request, queryset):
        approved_count = 0
        for transfer in queryset.filter(status='AML_SUSPENDED'):
            with transaction.atomic():
                transfer = Transfer.objects.select_for_update().get(id=transfer.id)
                account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
                
                transfer.status = 'PENDING'
                transfer.save(update_fields=['status'])

                if transfer.system_route == 'INTERNAL':
                    receiver = Account.objects.select_for_update().get(iban=transfer.recipient_iban)
                    account.blocked_funds -= transfer.amount
                    account.balance -= transfer.amount
                    receiver.balance += transfer.amount
                    account.save(update_fields=['blocked_funds', 'balance'])
                    receiver.save(update_fields=['balance'])
                    transfer.status = 'COMPLETED'
                    transfer.save(update_fields=['status'])
                elif transfer.system_route == 'ELIXIR':
                    from .services import ElixirIntegrationService
                    ElixirIntegrationService.send_transfer(transfer)
                elif transfer.system_route == 'EXPRESS_ELIXIR':
                    from .services import ExpressElixirIntegrationService
                    ExpressElixirIntegrationService.send_transfer(transfer)
                elif transfer.system_route == 'SORBNET':
                    from .services import SorbnetIntegrationService
                    sorbnet_status = SorbnetIntegrationService.send_transfer(transfer)
                    if sorbnet_status == 'SETTLED':
                        transfer.status = 'COMPLETED'
                        account.balance -= transfer.amount
                        account.blocked_funds -= transfer.amount
                    elif sorbnet_status == 'REJECTED':
                        transfer.status = 'FAILED'
                        account.blocked_funds -= transfer.amount
                    transfer.save(update_fields=['status'])
                    account.save(update_fields=['balance', 'blocked_funds'])
                elif transfer.system_route == 'SWIFT':
                    from .services import SwiftIntegrationService
                    uetr = SwiftIntegrationService.send_transfer(transfer)
                    transfer.swift_uetr = uetr
                    transfer.save(update_fields=['swift_uetr'])

                approved_count += 1
                
        self.message_user(request, f"Pomyślnie zaakceptowano i przesłano do realizacji {approved_count} przelewów.", messages.SUCCESS)

    @admin.action(description='ODRZUĆ Wyjaśnienie AML i cofnij przelew')
    def reject_aml(self, request, queryset):
        rejected_count = 0
        for transfer in queryset.filter(status='AML_SUSPENDED'):
            with transaction.atomic():
                transfer = Transfer.objects.select_for_update().get(id=transfer.id)
                account = Account.objects.select_for_update().get(id=transfer.sender_account.id)
                
                transfer.status = 'FAILED'
                transfer.save(update_fields=['status'])
                
                account.blocked_funds -= transfer.amount
                account.save(update_fields=['blocked_funds'])
                
                rejected_count += 1
                
        self.message_user(request, f"Pomyślnie odrzucono {rejected_count} przelewów. Środki wróciły do klientów.", messages.WARNING)
