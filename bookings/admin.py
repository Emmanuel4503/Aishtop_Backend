from django.contrib import admin
from .models import ServiceCategory, Service, Booking, WalletTransaction

@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'description')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'duration_minutes', 'is_active', 'created_at')
    list_filter = ('category', 'is_active')
    search_fields = ('name', 'description')
    ordering = ('category', 'name')


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'ticket_id', 'get_customer', 'service', 'worker', 
        'booking_type', 'payment_method', 'payment_status', 
        'service_status', 'total_price', 'created_at'
    )
    list_filter = (
        'service_status', 'payment_status', 'booking_type', 
        'payment_method', 'service', 'worker'
    )
    search_fields = (
        'ticket_id', 'user__email', 'user__full_name', 
        'guest_name', 'guest_email', 'payment_reference', 
        'monnify_transaction_reference'
    )
    readonly_fields = ('ticket_id', 'payment_reference', 'created_at', 'updated_at')
    ordering = ('-created_at',)

    def get_customer(self, obj):
        if obj.user:
            return f"{obj.user.full_name} ({obj.user.email})"
        return f"Guest: {obj.guest_name}"
    get_customer.short_description = "Customer"


@admin.register(WalletTransaction)
class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'transaction_type', 'payment_method', 'payment_status', 'payment_reference', 'created_at')
    list_filter = ('transaction_type', 'payment_method', 'payment_status')
    search_fields = ('user__email', 'user__full_name', 'payment_reference')
    readonly_fields = ('payment_reference', 'created_at')
    ordering = ('-created_at',)
