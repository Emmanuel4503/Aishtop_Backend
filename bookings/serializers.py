from rest_framework import serializers
from accounts.serializers import UserSerializer
from .models import ServiceCategory, Service, Booking, WalletTransaction

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = ('id', 'category', 'name', 'description', 'price', 'duration_minutes', 'is_active', 'image', 'created_at')


class ServiceCategorySerializer(serializers.ModelSerializer):
    services = ServiceSerializer(many=True, read_only=True)

    class Meta:
        model = ServiceCategory
        fields = ('id', 'name', 'slug', 'description', 'services')


from accounts.models import CustomUser

class BookingSerializer(serializers.ModelSerializer):
    service_details = ServiceSerializer(source='service', read_only=True)
    additional_services_details = ServiceSerializer(source='additional_services', many=True, read_only=True)
    additional_services = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Service.objects.all(),
        required=False,
    )
    services_details = serializers.SerializerMethodField(read_only=True)
    user_details = UserSerializer(source='user', read_only=True)
    worker_details = UserSerializer(source='worker', read_only=True)
    workers = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=CustomUser.objects.filter(role='worker'),
        required=False
    )
    workers_details = UserSerializer(source='workers', many=True, read_only=True)

    class Meta:
        model = Booking
        fields = (
            'id', 'ticket_id', 'user', 'user_details',
            'guest_name', 'guest_email', 'guest_phone',
            'service', 'service_details',
            'additional_services', 'additional_services_details',
            'services_details',
            'worker', 'worker_details',
            'workers', 'workers_details',
            'booking_type', 'scheduled_date', 'scheduled_time',
            'base_price', 'discount_applied', 'vat_amount', 'total_price',
            'payment_method', 'payment_status', 'service_status',
            'payment_reference', 'monnify_transaction_reference',
            'created_at', 'updated_at'
        )
        read_only_fields = (
            'id', 'ticket_id', 'payment_reference', 'monnify_transaction_reference',
            'base_price', 'discount_applied', 'vat_amount', 'total_price',
            'payment_status', 'service_status'
        )

    def get_services_details(self, obj):
        services = []
        if obj.service:
            services.append(obj.service)
        if obj.id:
            services.extend(list(obj.additional_services.all()))
        return ServiceSerializer(services, many=True).data

    def validate(self, attrs):
        booking_type = attrs.get('booking_type', 'walk_in')
        
        # If scheduled, date and time are required
        if booking_type == 'scheduled':
            if not attrs.get('scheduled_date'):
                raise serializers.ValidationError({"scheduled_date": "This field is required for scheduled appointments."})
            if not attrs.get('scheduled_time'):
                raise serializers.ValidationError({"scheduled_time": "This field is required for scheduled appointments."})

        # Check user authentication context for guest fields
        request = self.context.get('request')
        is_authenticated = request and request.user and request.user.is_authenticated

        if not is_authenticated:
            if not attrs.get('guest_name'):
                raise serializers.ValidationError({"guest_name": "This field is required for guest bookings."})
            if not attrs.get('guest_email'):
                raise serializers.ValidationError({"guest_email": "This field is required for guest bookings."})
            if not attrs.get('guest_phone'):
                raise serializers.ValidationError({"guest_phone": "This field is required for guest bookings."})
        
        return attrs


class WalletTransactionSerializer(serializers.ModelSerializer):
    user_details = UserSerializer(source='user', read_only=True)

    class Meta:
        model = WalletTransaction
        fields = ('id', 'user', 'user_details', 'amount', 'transaction_type', 'payment_method', 'payment_status', 'payment_reference', 'created_at')
        read_only_fields = ('id', 'payment_reference', 'payment_status', 'created_at')
