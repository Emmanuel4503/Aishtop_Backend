from django.urls import path
from .views import (
    list_services,
    get_service_detail,
    create_booking,
    list_user_bookings,
    init_wallet_deposit,
    list_wallet_transactions,
    monnify_webhook,
    worker_verify_ticket,
    worker_start_service,
    worker_complete_service,
    list_membership_levels,
    list_public_workers,
    worker_list_jobs,
    mock_payment_success,
    verify_payment,
    guest_booking_confirmation,
)

urlpatterns = [
    # Customer/Guest Booking endpoints
    path('services/', list_services, name='services_list'),
    path('services/<int:pk>/', get_service_detail, name='service_detail'),
    path('bookings/', create_booking, name='booking_create'),
    path('bookings/history/', list_user_bookings, name='booking_history'),
    path('membership-levels/', list_membership_levels, name='membership_levels_list'),
    path('workers/', list_public_workers, name='public_workers_list'),
    
    # Payment / Wallet endpoints
    path('payments/wallet-deposit/', init_wallet_deposit, name='wallet_deposit_init'),
    path('payments/wallet-transactions/', list_wallet_transactions, name='wallet_transactions_list'),
    path('payments/monnify-webhook/', monnify_webhook, name='monnify_webhook_callback'),
    path('payments/mock-success/', mock_payment_success, name='mock_payment_success'),
    path('payments/verify/', verify_payment, name='verify_payment'),
    path('bookings/guest-confirmation/', guest_booking_confirmation, name='guest_booking_confirmation'),
    
    # Worker endpoints
    path('worker/verify-ticket/', worker_verify_ticket, name='worker_verify_ticket'),
    path('worker/start-service/', worker_start_service, name='worker_start_service'),
    path('worker/complete-service/', worker_complete_service, name='worker_complete_service'),
    path('worker/jobs/', worker_list_jobs, name='worker_list_jobs'),
]
