from rest_framework import serializers
from .models import WorkerAttendance


class WorkerAttendanceSerializer(serializers.ModelSerializer):
    worker_name = serializers.CharField(source='worker.full_name', read_only=True)
    worker_id = serializers.IntegerField(source='worker.id', read_only=True)
    hours_worked = serializers.FloatField(read_only=True)

    class Meta:
        model = WorkerAttendance
        fields = [
            'id', 'worker_id', 'worker_name', 'date',
            'sign_in_time', 'sign_out_time', 'hours_worked',
        ]
