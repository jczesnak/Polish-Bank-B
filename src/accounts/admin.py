from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Account


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'pesel', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'pesel')
    ordering = ('email',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Dane bankowe', {'fields': ('pesel', 'phone_number')}),
    )


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ('iban', 'user', 'account_type', 'balance', 'currency', 'created_at')
    list_filter = ('account_type', 'currency')
    search_fields = ('iban', 'user__email')
    readonly_fields = ('id', 'iban', 'created_at')
