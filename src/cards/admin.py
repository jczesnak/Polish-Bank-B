from django.contrib import admin

from .models import CardTransaction, PrepaidCard


@admin.register(PrepaidCard)
class PrepaidCardAdmin(admin.ModelAdmin):
    list_display = ('masked_number', 'owner', 'account', 'status', 'daily_limit', 'created_at')
    list_filter = ('status',)
    search_fields = ('masked_number', 'owner__email', 'account__iban')
    readonly_fields = ('id', 'created_at')


@admin.register(CardTransaction)
class CardTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_name', 'card', 'amount', 'transaction_type', 'status', 'created_at')
    list_filter = ('transaction_type', 'status')
    search_fields = ('merchant_name', 'card__masked_number', 'account__iban')
    readonly_fields = ('id', 'created_at', 'processed_at')
