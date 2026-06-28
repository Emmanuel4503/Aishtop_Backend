from django.urls import path
from .views import (
    list_workers_for_attendance,
    record_attendance,
    admin_attendance_by_date,
    admin_worker_attendance_history,
)

urlpatterns = [
    # Public (QR page)
    path('workers/', list_workers_for_attendance, name='attendance_workers'),
    path('record/', record_attendance, name='attendance_record'),

    # Admin
    path('admin/by-date/', admin_attendance_by_date, name='attendance_by_date'),
    path('admin/worker/<int:worker_id>/', admin_worker_attendance_history, name='attendance_worker_history'),
]
