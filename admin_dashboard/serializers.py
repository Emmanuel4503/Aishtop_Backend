from rest_framework import serializers
from accounts.models import MembershipLevel

class MembershipLevelSerializer(serializers.ModelSerializer):
    class Meta:
        model = MembershipLevel
        fields = ('id', 'name', 'min_deposit_amount', 'discount_percentage', 'description')


class RescheduleBookingRequestSerializer(serializers.Serializer):
    scheduled_date = serializers.DateField(required=True, help_text="New appointment date (YYYY-MM-DD)")
    scheduled_time = serializers.TimeField(required=True, help_text="New appointment time (HH:MM:SS)")
