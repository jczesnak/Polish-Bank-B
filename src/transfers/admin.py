from django.contrib import admin
from .models import Transfer


@admin.register(Transfer)
class TransferAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender_account', 'recipient_iban', 'amount', 'system_route', 'status', 'created_at')
    list_filter = ('system_route', 'status')
    search_fields = ('recipient_iban', 'recipient_name', 'title')
    readonly_fields = ('id', 'created_at', 'processed_at')
