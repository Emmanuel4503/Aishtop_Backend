from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    membership_level = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            'id', 'email', 'full_name', 'phone_number', 'role', 
            'is_verified', 'date_joined', 'wallet_balance', 
            'total_deposited', 'membership_level', 'worker_status',
            'jobs_completed_override', 'revenue_generated_override',
            'worker_role'
        )
        read_only_fields = ('id', 'is_verified', 'date_joined', 'wallet_balance', 'total_deposited')

    def get_membership_level(self, obj):
        level = obj.membership_level
        if level:
            return {
                'id': level.id,
                'name': level.name,
                'discount_percentage': float(level.discount_percentage)
            }
        return None


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    class Meta:
        model = User
        fields = ('email', 'full_name', 'phone_number', 'role', 'password')
        extra_kwargs = {
            'phone_number': {'required': False},
            'role': {'required': False}
        }

    def validate_password(self, value):
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            email=validated_data['email'],
            full_name=validated_data['full_name'],
            password=validated_data['password'],
            phone_number=validated_data.get('phone_number', ''),
            role=validated_data.get('role', 'customer'),
            is_verified=True
        )

class UserLoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

class EmailVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(max_length=6, min_length=6, required=True)

class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)

class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    code = serializers.CharField(max_length=6, min_length=6, required=True)
    new_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, required=True, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value

# Custom Serializers for Swagger Schema documentation
class TokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="JWT access token")
    access_expires = serializers.DateTimeField(help_text="Access token expiry timestamp")
    refresh = serializers.CharField(help_text="JWT refresh token")
    refresh_expires = serializers.DateTimeField(help_text="Refresh token expiry timestamp")
    user = UserSerializer()

class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=True, help_text="JWT refresh token")

class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="New JWT access token")
    access_expires = serializers.DateTimeField(help_text="Access token expiry timestamp")

class RegisterResponseSerializer(serializers.Serializer):
    status = serializers.CharField(default="success")
    message = serializers.CharField(default="Registration successful! A 6-digit email verification code has been sent.")
    user = UserSerializer()

