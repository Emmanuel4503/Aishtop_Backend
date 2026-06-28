from django.contrib import admin
from .models import WorkerAttendance


@admin.register(WorkerAttendance)
class WorkerAttendanceAdmin(admin.ModelAdmin):
    list_display = ('worker', 'date', 'sign_in_time', 'sign_out_time', 'hours_worked')
    list_filter = ('date',)
    search_fields = ('worker__full_name', 'worker__email')
    ordering = ('-date',)
    readonly_fields = ('created_at', 'updated_at')
