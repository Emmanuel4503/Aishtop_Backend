from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken
from datetime import datetime, timedelta
from django.utils import timezone

from .models import OTPCode

User = get_user_model()

class CustomUserModelTests(APITestCase):
    def test_create_user(self):
        user = User.objects.create_user(
            email='test@example.com',
            full_name='Test User',
            password='testpassword123',
            phone_number='1234567890',
            role='customer'
        )
        self.assertEqual(user.email, 'test@example.com')
        self.assertEqual(user.full_name, 'Test User')
        self.assertFalse(user.is_verified)  # Default should be False

    def test_create_superuser(self):
        superuser = User.objects.create_superuser(
            email='admin@example.com',
            full_name='Admin User',
            password='adminpassword123'
        )
        self.assertEqual(superuser.email, 'admin@example.com')
        self.assertTrue(superuser.is_verified)  # Admin should be auto-verified


class AuthenticationAPITests(APITestCase):
    def setUp(self):
        self.register_url = reverse('auth_register')
        self.verify_url = reverse('auth_verify_email')
        self.login_url = reverse('auth_login')
        self.refresh_url = reverse('auth_refresh')
        self.profile_url = reverse('auth_profile')
        self.forgot_url = reverse('auth_forgot_password')
        self.reset_url = reverse('auth_reset_password')
        self.change_url = reverse('auth_change_password')
        
        # Create a base user
        self.test_password = 'testpassword123!'
        self.test_user = User.objects.create_user(
            email='john@example.com',
            full_name='John Doe',
            password=self.test_password,
            phone_number='+2348012345678',
            role='customer'
        )

    def test_register_user_sends_verification_otp(self):
        data = {
            'email': 'newuser@example.com',
            'full_name': 'New User',
            'phone_number': '+2348000000000',
            'role': 'customer',
            'password': 'StrongPassword123!'
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('verification code', response.data['message'])
        
        # Verify OTP record was generated in the DB
        new_user = User.objects.get(email='newuser@example.com')
        self.assertFalse(new_user.is_verified)
        otp = OTPCode.objects.filter(user=new_user, code_type='email_verification').first()
        self.assertIsNotNone(otp)
        self.assertEqual(len(otp.code), 6)

    def test_login_blocked_for_unverified_user(self):
        # self.test_user is not verified by default in setUp
        data = {
            'email': 'john@example.com',
            'password': self.test_password
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data['status'], 'unverified')
        self.assertIn('not verified', response.data['detail'])

    def test_verify_email_success(self):
        # Create verification code
        otp = OTPCode.objects.create(
            user=self.test_user,
            code='123456',
            code_type='email_verification'
        )
        
        data = {
            'email': 'john@example.com',
            'code': '123456'
        }
        response = self.client.post(self.verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        self.test_user.refresh_from_db()
        self.assertTrue(self.test_user.is_verified)
        
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_verify_email_invalid_or_expired_code(self):
        # Create expired code
        otp = OTPCode.objects.create(
            user=self.test_user,
            code='123456',
            code_type='email_verification'
        )
        # Manually alter created_at to force expiration
        otp.created_at = timezone.now() - timedelta(minutes=20)
        otp.save()
        
        # Try verifying with expired code
        data = {
            'email': 'john@example.com',
            'code': '123456'
        }
        response = self.client.post(self.verify_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
        self.assertFalse(self.test_user.is_verified)

    def test_login_success_after_verification_with_token_expiry(self):
        # Verify the user first
        self.test_user.is_verified = True
        self.test_user.save()
        
        data = {
            'email': 'john@example.com',
            'password': self.test_password
        }
        response = self.client.post(self.login_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data)
        self.assertIn('access_expires', response.data)
        self.assertIn('refresh', response.data)
        self.assertIn('refresh_expires', response.data)
        
        # Confirm they are valid ISO timestamps
        access_exp = datetime.fromisoformat(response.data['access_expires'])
        self.assertGreater(access_exp, timezone.now())

    def test_refresh_token_with_expiry(self):
        # Generate token
        refresh = RefreshToken.for_user(self.test_user)
        data = {
            'refresh': str(refresh)
        }
        response = self.client.post(self.refresh_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        self.assertIn('access', response.data)
        self.assertIn('access_expires', response.data)

    def test_forgot_password_generates_otp(self):
        data = {
            'email': 'john@example.com'
        }
        response = self.client.post(self.forgot_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        # Check that a password reset OTP was created in DB
        otp = OTPCode.objects.filter(user=self.test_user, code_type='password_reset').first()
        self.assertIsNotNone(otp)

    def test_reset_password_success(self):
        # Generate OTP
        otp = OTPCode.objects.create(
            user=self.test_user,
            code='654321',
            code_type='password_reset'
        )
        
        data = {
            'email': 'john@example.com',
            'code': '654321',
            'new_password': 'NewSuperSecurePassword123!'
        }
        response = self.client.post(self.reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        # Verify password updated
        self.test_user.refresh_from_db()
        self.assertTrue(self.test_user.check_password('NewSuperSecurePassword123!'))
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)

    def test_change_password_success(self):
        # Create token
        refresh = RefreshToken.for_user(self.test_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        data = {
            'old_password': self.test_password,
            'new_password': 'UpdatedPassword123!'
        }
        response = self.client.post(self.change_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        self.test_user.refresh_from_db()
        self.assertTrue(self.test_user.check_password('UpdatedPassword123!'))

    def test_change_password_invalid_old_password(self):
        refresh = RefreshToken.for_user(self.test_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        
        data = {
            'old_password': 'incorrectpassword',
            'new_password': 'UpdatedPassword123!'
        }
        response = self.client.post(self.change_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['status'], 'error')
