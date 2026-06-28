from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

class CustomUserManager(BaseUserManager):
    def create_user(self, email, full_name, password=None, role='customer', **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, full_name=full_name, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, full_name, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_verified', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, full_name, password, role='owner', **extra_fields)

class MembershipLevel(models.Model):
    name = models.CharField(max_length=50, unique=True)
    min_deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)  # e.g., 5.00 for 5%
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.name} (Min Dep: {self.min_deposit_amount}, Discount: {self.discount_percentage}%)"


class CustomUser(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('worker', 'Worker'),
        ('front_desk', 'Front Desk'),
        ('owner', 'Owner/Admin'),
    )

    WORKER_STATUS_CHOICES = (
        ('available', 'Available'),
        ('busy', 'Busy'),
    )

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='customer')
    
    # Wallet & Worker Fields
    wallet_balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_deposited = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    worker_status = models.CharField(max_length=20, choices=WORKER_STATUS_CHOICES, default='available')
    worker_role = models.CharField(max_length=100, blank=True, null=True)
    jobs_completed_override = models.IntegerField(default=0)
    revenue_generated_override = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    @property
    def membership_level(self):
        # Returns the highest membership level user qualifies for based on total_deposited
        levels = MembershipLevel.objects.all().order_by('-min_deposit_amount')
        for level in levels:
            if self.total_deposited >= level.min_deposit_amount:
                return level
        return None

    @property
    def discount_percentage(self):
        level = self.membership_level
        if level:
            return level.discount_percentage
        return 0.00


    def __str__(self):
        return f"{self.email} ({self.role})"


class OTPCode(models.Model):
    CODE_TYPES = (
        ('email_verification', 'Email Verification'),
        ('password_reset', 'Password Reset'),
    )
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    code_type = models.CharField(max_length=20, choices=CODE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    def is_expired(self):
        from django.utils import timezone
        from datetime import timedelta
        return timezone.now() > self.created_at + timedelta(minutes=15)

    def __str__(self):
        return f"{self.user.email} - {self.code_type} - {self.code}"

