from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.utils import timezone
from decimal import Decimal

from accounts.models import MembershipLevel
from bookings.models import ServiceCategory, Service, Booking

User = get_user_model()

class AdminDashboardTests(APITestCase):
    def setUp(self):
        # Create users
        self.owner = User.objects.create_user(
            email="owner@example.com",
            full_name="Steve Owner",
            password="ownerpass123",
            role="owner",
            is_verified=True
        )
        
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

        # Create basic category & service
        self.category = ServiceCategory.objects.create(name="Pedicure", slug="pedicure")
        self.service = Service.objects.create(
            category=self.category,
            name="Male Pedicure",
            price=Decimal("15000.00"),
            duration_minutes=45
        )

        # URLs
        self.cat_list_url = reverse('admin_category_list_create')
        self.svc_list_url = reverse('admin_service_list_create')
        self.membership_list_url = reverse('admin_membership_list_create')
        self.bookings_url = reverse('admin_list_bookings')
        
        self.revenue_url = reverse('admin_revenue_metrics')
        self.customer_metrics_url = reverse('admin_customer_metrics')
        self.worker_metrics_url = reverse('admin_worker_metrics')

    def test_authorization_rejected_for_customer(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.get(self.revenue_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorization_rejected_for_worker(self):
        self.client.force_authenticate(user=self.worker)
        response = self.client.get(self.revenue_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_authorization_allowed_for_owner(self):
        self.client.force_authenticate(user=self.owner)
        response = self.client.get(self.revenue_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_category_crud_by_owner(self):
        self.client.force_authenticate(user=self.owner)
        
        # 1. Create Category
        data = {"name": "New Category", "slug": "new-category", "description": "New desc"}
        response = self.client.post(self.cat_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_cat_id = response.data['data']['id']
        
        # 2. Update Category
        detail_url = reverse('admin_category_detail', kwargs={'pk': new_cat_id})
        update_data = {"name": "Updated Category", "slug": "updated-category"}
        response = self.client.put(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['name'], "Updated Category")
        
        # 3. Delete Category
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(ServiceCategory.objects.filter(id=new_cat_id).exists())

    def test_service_crud_by_owner(self):
        self.client.force_authenticate(user=self.owner)
        
        # 1. Create Service
        data = {
            "category": self.category.id,
            "name": "Foot Spa",
            "price": "8000.00",
            "duration_minutes": 30
        }
        response = self.client.post(self.svc_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_svc_id = response.data['data']['id']
        
        # 2. Update Service
        detail_url = reverse('admin_service_detail', kwargs={'pk': new_svc_id})
        update_data = {"price": "9500.00"}
        response = self.client.put(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['data']['price']), 9500.00)
        
        # 3. Delete Service
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Service.objects.filter(id=new_svc_id).exists())

    def test_membership_level_crud_by_owner(self):
        self.client.force_authenticate(user=self.owner)
        
        # 1. Create Level
        data = {
            "name": "Diamond",
            "min_deposit_amount": "250000.00",
            "discount_percentage": "20.00",
            "description": "20% off"
        }
        response = self.client.post(self.membership_list_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_level_id = response.data['data']['id']
        
        # 2. Update Level
        detail_url = reverse('admin_membership_detail', kwargs={'pk': new_level_id})
        update_data = {"discount_percentage": "25.00"}
        response = self.client.put(detail_url, update_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(float(response.data['data']['discount_percentage']), 25.00)
        
        # 3. Delete Level
        response = self.client.delete(detail_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(MembershipLevel.objects.filter(id=new_level_id).exists())

    def test_bookings_metrics_reschedule_cancel(self):
        # Create a booking
        booking = Booking.objects.create(
            user=self.customer,
            service=self.service,
            booking_type="walk_in",
            base_price=Decimal("15000.00"),
            discount_applied=Decimal("0.00"),
            vat_amount=Decimal("150.00"),
            total_price=Decimal("15150.00"),
            payment_method="monnify",
            payment_status="paid",
            service_status="waiting"
        )
        
        self.client.force_authenticate(user=self.owner)
        
        # 1. Reschedule Booking
        reschedule_url = reverse('admin_reschedule_booking', kwargs={'ticket_id': booking.ticket_id})
        reschedule_data = {
            "scheduled_date": "2026-07-01",
            "scheduled_time": "14:30:00"
        }
        response = self.client.post(reschedule_url, reschedule_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(str(booking.scheduled_date), "2026-07-01")
        self.assertEqual(str(booking.scheduled_time), "14:30:00")
        self.assertEqual(booking.booking_type, "scheduled")
        
        # 2. Cancel Booking
        cancel_url = reverse('admin_cancel_booking', kwargs={'ticket_id': booking.ticket_id})
        response = self.client.post(cancel_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        booking.refresh_from_db()
        self.assertEqual(booking.service_status, "cancelled")

    def test_analytics_endpoints(self):
        # Create paid bookings
        Booking.objects.create(
            user=self.customer,
            service=self.service,
            booking_type="walk_in",
            base_price=Decimal("15000.00"),
            discount_applied=Decimal("0.00"),
            vat_amount=Decimal("150.00"),
            total_price=Decimal("15150.00"),
            payment_method="monnify",
            payment_status="paid",
            service_status="completed",
            worker=self.worker
        )
        
        self.client.force_authenticate(user=self.owner)
        
        # Revenue metrics
        response = self.client.get(self.revenue_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['data']['overall_revenue'], 15150.00)
        self.assertEqual(response.data['data']['monnify_payments'], 15150.00)
        
        # Customer metrics
        response = self.client.get(self.customer_metrics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['total_bookings'], 1)
        self.assertEqual(response.data['data'][0]['total_spent'], 15150.00)
        
        # Worker metrics
        response = self.client.get(self.worker_metrics_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['data']), 1)
        self.assertEqual(response.data['data'][0]['completed_jobs'], 1)
        self.assertEqual(response.data['data'][0]['revenue_generated'], 15150.00)
