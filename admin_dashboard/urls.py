from django.urls import path
from .views import (
    admin_category_list_create,
    admin_category_detail,
    admin_service_list_create,
    admin_service_detail,
    admin_membership_list_create,
    admin_membership_detail,
    admin_list_bookings,
    admin_reschedule_booking,
    admin_cancel_booking,
    admin_revenue_metrics,
    admin_customer_metrics,
    admin_worker_metrics,
    admin_create_worker,
    admin_edit_worker,
    admin_delete_worker,
    admin_assign_worker,
    admin_wallet_metrics
)

urlpatterns = [
    # Category CRUD
    path('categories/', admin_category_list_create, name='admin_category_list_create'),
    path('categories/<int:pk>/', admin_category_detail, name='admin_category_detail'),
    
    # Service CRUD
    path('services/', admin_service_list_create, name='admin_service_list_create'),
    path('services/<int:pk>/', admin_service_detail, name='admin_service_detail'),
    
    # Membership Level CRUD
    path('membership-levels/', admin_membership_list_create, name='admin_membership_list_create'),
    path('membership-levels/<int:pk>/', admin_membership_detail, name='admin_membership_detail'),
    
    # Queue / Booking Management
    path('bookings/', admin_list_bookings, name='admin_list_bookings'),
    path('bookings/<str:ticket_id>/reschedule/', admin_reschedule_booking, name='admin_reschedule_booking'),
    path('bookings/<str:ticket_id>/cancel/', admin_cancel_booking, name='admin_cancel_booking'),
    path('bookings/<str:ticket_id>/assign-worker/', admin_assign_worker, name='admin_assign_worker'),
    
    # Analytics / Metrics
    path('revenue/', admin_revenue_metrics, name='admin_revenue_metrics'),
    path('customers/', admin_customer_metrics, name='admin_customer_metrics'),
    path('workers/', admin_worker_metrics, name='admin_worker_metrics'),
    path('workers/create/', admin_create_worker, name='admin_create_worker'),
    path('workers/<int:pk>/edit/', admin_edit_worker, name='admin_edit_worker'),
    path('workers/<int:pk>/delete/', admin_delete_worker, name='admin_delete_worker'),
    path('wallet/', admin_wallet_metrics, name='admin_wallet_metrics'),
]
