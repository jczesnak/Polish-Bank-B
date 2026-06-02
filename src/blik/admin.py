from django.contrib import admin
from .models import BlikCode, BlikTransaction, PhoneAlias, P2pContact


@admin.register(BlikCode)
class BlikCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'user', 'account', 'status', 'expires_at', 'created_at')
    list_filter = ('status',)
    search_fields = ('code', 'user__email')
    readonly_fields = ('id', 'created_at')


@admin.register(BlikTransaction)
class BlikTransactionAdmin(admin.ModelAdmin):
    list_display = ('klik_transaction_id', 'user', 'amount', 'currency', 'merchant_name', 'status', 'created_at')
    list_filter = ('status', 'currency')
    search_fields = ('klik_transaction_id', 'user__email', 'merchant_name')
    readonly_fields = ('id', 'created_at')


@admin.register(PhoneAlias)
class PhoneAliasAdmin(admin.ModelAdmin):
    list_display = ('phone', 'user', 'account', 'zone', 'klik_alias_id', 'created_at')
    list_filter = ('zone',)
    search_fields = ('phone', 'user__email', 'account__iban')
    readonly_fields = ('id', 'created_at')


@admin.register(P2pContact)
class P2pContactAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'user', 'created_at')
    search_fields = ('name', 'phone', 'user__email')
    readonly_fields = ('id', 'created_at')
