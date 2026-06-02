from django.contrib import admin
from .models import ApprovalRequest, Transfer


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender_account', 'recipient_iban', 'amount', 'system_route', 'status', 'created_at')
    list_filter = ('system_route', 'status')
    search_fields = ('recipient_iban', 'recipient_name', 'title')
    readonly_fields = ('id', 'created_at', 'processed_at')


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'request_type', 'status', 'junior', 'parent', 'account', 'created_at', 'decided_at')
    list_filter = ('request_type', 'status')
    search_fields = ('junior__email', 'parent__email', 'account__iban')
    readonly_fields = ('id', 'created_at', 'decided_at')
