from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, MembershipLevel, OTPCode

@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('email', 'full_name', 'role', 'wallet_balance', 'total_deposited', 'is_verified', 'is_active', 'date_joined')
    list_filter = ('role', 'is_verified', 'is_active')
    search_fields = ('email', 'full_name', 'phone_number')
    ordering = ('-date_joined',)
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('full_name', 'phone_number')}),
        ('Role & Verification', {'fields': ('role', 'is_verified', 'is_active')}),
        ('Wallet Info', {'fields': ('wallet_balance', 'total_deposited', 'worker_status')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    readonly_fields = ('date_joined',)


@admin.register(MembershipLevel)
class MembershipLevelAdmin(admin.ModelAdmin):
    list_display = ('name', 'min_deposit_amount', 'discount_percentage', 'description')
    search_fields = ('name',)
    ordering = ('min_deposit_amount',)


@admin.register(OTPCode)
class OTPCodeAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'code_type', 'created_at', 'is_used')
    list_filter = ('code_type', 'is_used')
    search_fields = ('user__email', 'code')
    readonly_fields = ('created_at',)
