from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from decimal import Decimal
import json

from accounts.models import MembershipLevel
from bookings.models import ServiceCategory, Service, Booking, WalletTransaction

User = get_user_model()

class BookingServiceTests(APITestCase):
    def setUp(self):
        # Create categories and services
        self.category = ServiceCategory.objects.create(name="Barbing", slug="barbing", description="Haircut services")
        self.service = Service.objects.create(
            category=self.category,
            name="Adult Haircut",
            price=Decimal("3000.00"),
            duration_minutes=30
        )
        
        # Create membership levels
        self.silver = MembershipLevel.objects.create(name="Silver", min_deposit_amount=Decimal("10000.00"), discount_percentage=Decimal("5.00"))
        self.gold = MembershipLevel.objects.create(name="Gold", min_deposit_amount=Decimal("50000.00"), discount_percentage=Decimal("10.00"))
        self.vip = MembershipLevel.objects.create(name="VIP", min_deposit_amount=Decimal("100000.00"), discount_percentage=Decimal("15.00"))

        # Create users
        self.customer = User.objects.create_user(
            email="customer@example.com",
            full_name="John Customer",
            password="customerpass123",
            role="customer",
            is_verified=True
        )
        
        self.worker = User.objects.create_user(
            email="worker@example.com",
            full_name="Mike Worker",
            password="workerpass123",
            role="worker",
            is_verified=True
        )
        
        self.owner = User.objects.create_user(
            email="owner@example.com",
            full_name="Steve Owner",
            password="ownerpass123",
            role="owner",
            is_verified=True
        )

        self.list_services_url = reverse('services_list')
        self.create_booking_url = reverse('booking_create')
        self.booking_history_url = reverse('booking_history')
        self.wallet_deposit_url = reverse('wallet_deposit_init')
        self.webhook_url = reverse('monnify_webhook_callback')
        
        self.worker_verify_url = reverse('worker_verify_ticket')
        self.worker_start_url = reverse('worker_start_service')
        self.worker_complete_url = reverse('worker_complete_service')

    def test_list_services(self):
        response = self.client.get(self.list_services_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['name'], "Barbing")
        self.assertEqual(len(response.data['data'][0]['services']), 1)

    def test_create_booking_guest_monnify(self):
        data = {
            "service": self.service.id,
            "booking_type": "walk_in",
            "payment_method": "monnify",
            "guest_name": "Alice Guest",
            "guest_email": "alice@example.com",
            "guest_phone": "08011112222"
        }
        response = self.client.post(self.create_booking_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        
        booking_data = response.data['data']['booking']
        self.assertEqual(booking_data['guest_name'], "Alice Guest")
        self.assertEqual(float(booking_data['base_price']), 3000.00)
        self.assertEqual(float(booking_data['discount_applied']), 0.00)
        # 1% VAT
        self.assertEqual(float(booking_data['vat_amount']), 30.00)
        self.assertEqual(float(booking_data['total_price']), 3030.00)
        self.assertEqual(booking_data['payment_status'], "pending")
        self.assertEqual(booking_data['service_status'], "waiting")
        self.assertIn("checkout_url", response.data['data'])

    def test_create_booking_registered_wallet_insufficient_funds(self):
        self.client.force_authenticate(user=self.customer)
        data = {
            "service": self.service.id,
            "booking_type": "walk_in",
            "payment_method": "wallet"
        }
        response = self.client.post(self.create_booking_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertIn("Insufficient wallet balance", response.data['message'])

    def test_create_booking_registered_wallet_success_with_discount(self):
        # Fund wallet and give VIP level
        self.customer.total_deposited = Decimal("120000.00")
        self.customer.wallet_balance = Decimal("50000.00")
        self.customer.save()
        
        self.assertEqual(self.customer.membership_level.name, "VIP")
        self.assertEqual(self.customer.discount_percentage, Decimal("15.00"))
        
        self.client.force_authenticate(user=self.customer)
        data = {
            "service": self.service.id,
            "booking_type": "walk_in",
            "payment_method": "wallet"
        }
        response = self.client.post(self.create_booking_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        
        booking_data = response.data['data']['booking']
        self.assertEqual(float(booking_data['base_price']), 3000.00)
        # 15% discount on 3000 = 450
        self.assertEqual(float(booking_data['discount_applied']), 450.00)
        # Net price = 3000 - 450 = 2550
        # 1% VAT of 2550 = 25.50
        self.assertEqual(float(booking_data['vat_amount']), 25.50)
        # Total = 2550 + 25.50 = 2575.50
        self.assertEqual(float(booking_data['total_price']), 2575.50)
        self.assertEqual(booking_data['payment_status'], "paid")
        
        # Verify wallet balance deduction
        self.customer.refresh_from_db()
        self.assertEqual(float(self.customer.wallet_balance), 50000.00 - 2575.50)
        
        # Verify transaction log
        tx = WalletTransaction.objects.filter(user=self.customer, transaction_type='spend').first()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx.amount), 2575.50)
        self.assertEqual(tx.payment_status, 'success')

    def test_init_wallet_deposit(self):
        self.client.force_authenticate(user=self.customer)
        data = {"amount": "15000.00"}
        response = self.client.post(self.wallet_deposit_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn("checkout_url", response.data['data'])
        
        # Verify WalletTransaction created
        tx = WalletTransaction.objects.filter(user=self.customer, transaction_type='deposit').first()
        self.assertIsNotNone(tx)
        self.assertEqual(float(tx.amount), 15000.00)
        self.assertEqual(tx.payment_status, 'pending')

    def test_monnify_webhook_booking_payment(self):
        # Create a pending booking
        booking = Booking.objects.create(
            service=self.service,
            booking_type="walk_in",
            base_price=Decimal("3000.00"),
            discount_applied=Decimal("0.00"),
            vat_amount=Decimal("30.00"),
            total_price=Decimal("3030.00"),
            payment_method="monnify",
            payment_status="pending",
            service_status="waiting"
        )
        
        # Webhook event body
        payload = {
            "eventData": {
                "paymentReference": booking.payment_reference,
                "paymentStatus": "PAID",
                "transactionReference": "TX-12345678"
            }
        }
        
        # Mock webhook signature validation to bypass signature check in tests
        # We will manually pass a header, but since we are not calling monnify server,
        # let's mock verify_monnify_webhook_signature
        import unittest.mock as mock
        with mock.patch('bookings.views.verify_monnify_webhook_signature', return_value=True):
            response = self.client.post(self.webhook_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
        booking.refresh_from_db()
        self.assertEqual(booking.payment_status, 'paid')
        self.assertEqual(booking.monnify_transaction_reference, 'TX-12345678')
        
        # Since worker was available, it should have been auto-assigned!
        self.assertEqual(booking.service_status, 'assigned')
        self.assertEqual(booking.worker, self.worker)
        
        # Worker status should have become busy
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.worker_status, 'busy')

    def test_monnify_webhook_wallet_deposit(self):
        tx = WalletTransaction.objects.create(
            user=self.customer,
            amount=Decimal("25000.00"),
            transaction_type="deposit",
            payment_method="monnify",
            payment_status="pending"
        )
        
        payload = {
            "eventData": {
                "paymentReference": tx.payment_reference,
                "paymentStatus": "SUCCESSFUL",
                "transactionReference": "TX-9999"
            }
        }
        
        import unittest.mock as mock
        with mock.patch('bookings.views.verify_monnify_webhook_signature', return_value=True):
            response = self.client.post(self.webhook_url, payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            
        tx.refresh_from_db()
        self.assertEqual(tx.payment_status, 'success')
        
        self.customer.refresh_from_db()
        self.assertEqual(float(self.customer.wallet_balance), 25000.00)
        self.assertEqual(float(self.customer.total_deposited), 25000.00)
        
        # Membership Level upgrade: 25000 qualifies for Gold (since Gold threshold is 50000, wait, Gold is >= 50k, Silver is >= 10k. 25000 qualifies for Silver!)
        self.assertEqual(self.customer.membership_level.name, "Silver")

    def test_worker_lifecycle_and_queue(self):
        # 1. Authenticate worker
        self.client.force_authenticate(user=self.worker)
        
        # Create a paid walk-in booking - gets auto-assigned to worker since worker is available
        booking1 = Booking.objects.create(
            service=self.service,
            booking_type="walk_in",
            base_price=Decimal("3000.00"),
            discount_applied=Decimal("0.00"),
            vat_amount=Decimal("30.00"),
            total_price=Decimal("3030.00"),
            payment_method="monnify",
            payment_status="paid",
            service_status="waiting"
        )
        # Run auto-assign manually for setup
        from bookings.views import auto_assign_worker_for_booking
        auto_assign_worker_for_booking(booking1)
        booking1.refresh_from_db()
        self.worker.refresh_from_db()
        
        self.assertEqual(booking1.worker, self.worker)
        self.assertEqual(booking1.service_status, 'assigned')
        self.assertEqual(self.worker.worker_status, 'busy')
        
        # 2. Worker verifies ticket
        data = {"ticket_id": booking1.ticket_id}
        response = self.client.post(self.worker_verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['data']['service_name'], self.service.name)

        # 3. Worker starts service
        response = self.client.post(self.worker_start_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking1.refresh_from_db()
        self.assertEqual(booking1.service_status, 'in_progress')
        
        # 4. Create another paid walk-in booking while worker is busy. It must go to 'waiting' and remain unassigned.
        booking2 = Booking.objects.create(
            service=self.service,
            booking_type="walk_in",
            base_price=Decimal("3000.00"),
            discount_applied=Decimal("0.00"),
            vat_amount=Decimal("30.00"),
            total_price=Decimal("3030.00"),
            payment_method="monnify",
            payment_status="paid",
            service_status="waiting"
        )
        auto_assign_worker_for_booking(booking2)
        booking2.refresh_from_db()
        
        self.assertEqual(booking2.service_status, 'waiting')
        self.assertIsNone(booking2.worker)
        
        # 5. Worker completes service. Status becomes available, then queue auto-assigns booking2 to this worker and sets status back to busy!
        response = self.client.post(self.worker_complete_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        booking1.refresh_from_db()
        self.assertEqual(booking1.service_status, 'completed')
        
        # Verify booking2 is now assigned to the worker and worker is busy again
        booking2.refresh_from_db()
        self.assertEqual(booking2.service_status, 'assigned')
        self.assertEqual(booking2.worker, self.worker)
        
        self.worker.refresh_from_db()
        self.assertEqual(self.worker.worker_status, 'busy')
