from django.db import models
from django.conf import settings


class WorkerAttendance(models.Model):
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='attendance_records',
        limit_choices_to={'role': 'worker'},
    )
    date = models.DateField()
    sign_in_time = models.TimeField(null=True, blank=True)
    sign_out_time = models.TimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['worker', 'date']]
        ordering = ['-date', 'worker__full_name']

    def __str__(self):
        return f"{self.worker.full_name} — {self.date}"

    @property
    def hours_worked(self):
        if self.sign_in_time and self.sign_out_time:
            from datetime import datetime, date
            dt_in = datetime.combine(date.today(), self.sign_in_time)
            dt_out = datetime.combine(date.today(), self.sign_out_time)
            delta = dt_out - dt_in
            if delta.total_seconds() > 0:
                return round(delta.total_seconds() / 3600, 2)
        return None
