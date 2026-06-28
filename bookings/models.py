from django.db import models
from django.conf import settings
from django.utils import timezone
import random
import string

def generate_ticket_id():
    date_str = timezone.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return f"T-{date_str}-{random_str}"

def generate_payment_reference():
    date_str = timezone.now().strftime('%Y%m%d%H%M%S')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"REF-{date_str}-{random_str}"


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Service Categories"

    def __str__(self):
        return self.name


class Service(models.Model):
    category = models.ForeignKey(ServiceCategory, related_name='services', on_delete=models.CASCADE)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_minutes = models.IntegerField(default=30, help_text="Duration in minutes")
    is_active = models.BooleanField(default=True)
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} - ₦{self.price}"


class Booking(models.Model):
    BOOKING_TYPE_CHOICES = (
        ('walk_in', 'Walk-In / Proceed Now'),
        ('scheduled', 'Scheduled Appointment'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('wallet', 'Wallet'),
        ('monnify', 'Monnify Checkout'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
    )

    SERVICE_STATUS_CHOICES = (
        ('waiting', 'Waiting'),
        ('assigned', 'Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )

    ticket_id = models.CharField(max_length=50, unique=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='bookings'
    )
    
    # Guest User details
    guest_name = models.CharField(max_length=255, blank=True, null=True)
    guest_email = models.EmailField(blank=True, null=True)
    guest_phone = models.CharField(max_length=20, blank=True, null=True)

    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name='bookings')
    worker = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        limit_choices_to={'role': 'worker'}, 
        related_name='worker_bookings'
    )
    workers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='worker_bookings_m2m',
        blank=True,
        limit_choices_to={'role': 'worker'},
    )

    booking_type = models.CharField(max_length=20, choices=BOOKING_TYPE_CHOICES, default='walk_in')
    scheduled_date = models.DateField(blank=True, null=True)
    scheduled_time = models.TimeField(blank=True, null=True)

    # Prices and VAT
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_applied = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="1% Developer Split Amount")
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='monnify')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    service_status = models.CharField(max_length=20, choices=SERVICE_STATUS_CHOICES, default='waiting')

    additional_services = models.ManyToManyField(
        Service,
        related_name='additional_bookings',
        blank=True,
    )

    payment_reference = models.CharField(max_length=100, unique=True, blank=True)
    monnify_transaction_reference = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = generate_ticket_id()
        if not self.payment_reference:
            self.payment_reference = generate_payment_reference()
        super().save(*args, **kwargs)

    def __str__(self):
        customer = self.user.full_name if self.user else f"Guest ({self.guest_name})"
        return f"{self.ticket_id} - {customer} - {self.service.name} - {self.service_status}"


class WalletTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('deposit', 'Deposit'),
        ('spend', 'Spend'),
    )

    PAYMENT_METHOD_CHOICES = (
        ('monnify', 'Monnify'),
        ('wallet', 'Wallet Balance'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            self.payment_reference = generate_payment_reference()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.email} - {self.transaction_type} - ₦{self.amount} - {self.payment_status}"
