from datetime import datetime, timezone
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail, EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.crypto import get_random_string
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from drf_yasg.utils import swagger_auto_schema
import threading
import logging

logger = logging.getLogger(__name__)

def send_email_async(msg):
    def run():
        try:
            msg.send(fail_silently=False)
        except Exception as e:
            logger.error(f"Failed to send email asynchronously: {e}")
    threading.Thread(target=run).start()

from .models import OTPCode
from .serializers import (
    UserSerializer,
    UserRegisterSerializer,
    UserLoginSerializer,
    EmailVerificationSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
    ChangePasswordSerializer,
    TokenResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
    RegisterResponseSerializer
)

User = get_user_model()

@swagger_auto_schema(
    method='post',
    request_body=UserRegisterSerializer,
    responses={
        201: RegisterResponseSerializer(),
        400: 'Bad Request - Validation Errors'
    },
    operation_description="Registers a new user and sends a 6-digit email verification OTP code via ZeptoMail SMTP."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user, verify them automatically, and return credentials.
    """
    serializer = UserRegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Generate programmatic JWT Tokens using SimpleJWT
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        # Extract Expiry Timestamps
        access_expires = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
        refresh_expires = datetime.fromtimestamp(refresh['exp'], tz=timezone.utc)
        
        response_data = {
            'status': 'success',
            'message': 'Registration successful! Welcome to Aishtop.',
            'access': str(access_token),
            'access_expires': access_expires.isoformat(),
            'refresh': str(refresh),
            'refresh_expires': refresh_expires.isoformat(),
            'user': UserSerializer(user).data
        }
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    return Response({
        'status': 'error',
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


@swagger_auto_schema(
    method='post',
    request_body=UserLoginSerializer,
    responses={
        200: TokenResponseSerializer(),
        400: 'Bad Request - Missing credentials',
        401: 'Unauthorized - Invalid credentials',
        403: 'Forbidden - Account unverified'
    },
    operation_description="Authenticates credentials. Rejects unverified emails, returns JWT tokens and expiry timestamps if verified."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def login_user(request):
    """
    Log in a user. Blocks login if email is not verified. Returns tokens + expiry times.
    """
    serializer = UserLoginSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    email = serializer.validated_data['email']
    password = serializer.validated_data['password']

    user = authenticate(request, email=email, password=password)

    if user is not None:
        if not user.is_active:
            return Response({
                'status': 'error',
                'detail': 'User account is disabled.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Gate Login: Check if Email is Verified
        if not user.is_verified:
            return Response({
                'status': 'unverified',
                'detail': 'Your email address is not verified. Please verify your email before logging in.',
                'email': user.email
            }, status=status.HTTP_403_FORBIDDEN)
        
        # Generate programmatic JWT Tokens using SimpleJWT
        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token
        
        # Extract Expiry Timestamps
        access_expires = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
        refresh_expires = datetime.fromtimestamp(refresh['exp'], tz=timezone.utc)
        
        response_data = {
            'status': 'success',
            'access': str(access_token),
            'access_expires': access_expires.isoformat(),
            'refresh': str(refresh),
            'refresh_expires': refresh_expires.isoformat(),
            'user': UserSerializer(user).data
        }
        return Response(response_data, status=status.HTTP_200_OK)
    
    return Response({
        'status': 'error',
        'detail': 'Invalid email or password.'
    }, status=status.HTTP_401_UNAUTHORIZED)


@swagger_auto_schema(
    method='post',
    request_body=TokenRefreshRequestSerializer,
    responses={
        200: TokenRefreshResponseSerializer(),
        400: 'Bad Request - Missing token',
        401: 'Unauthorized - Invalid or expired token'
    },
    operation_description="Refreshes an expired access token using a valid refresh token. Returns new token & expiry."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def refresh_token(request):
    """
    Refresh JWT access token. Returns new access token + expiry.
    """
    serializer = TokenRefreshRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    refresh_token_str = serializer.validated_data['refresh']

    try:
        refresh = RefreshToken(refresh_token_str)
        access_token = refresh.access_token
        access_expires = datetime.fromtimestamp(access_token['exp'], tz=timezone.utc)
        
        response_data = {
            'status': 'success',
            'access': str(access_token),
            'access_expires': access_expires.isoformat()
        }
        return Response(response_data, status=status.HTTP_200_OK)
    except (TokenError, InvalidToken) as e:
        return Response({
            'status': 'error',
            'detail': str(e)
        }, status=status.HTTP_401_UNAUTHORIZED)


@swagger_auto_schema(
    method='post',
    request_body=EmailVerificationSerializer,
    responses={
        200: 'Success - Email verified',
        400: 'Bad Request - Validation / Incorrect OTP',
        404: 'Not Found - User not found'
    },
    operation_description="Verifies user's email using the 6-digit OTP code received via email."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def verify_email(request):
    """
    Verify user email using OTP code.
    """
    serializer = EmailVerificationSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
    
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'status': 'error',
            'detail': 'User account with this email does not exist.'
        }, status=status.HTTP_404_NOT_FOUND)
    
    if user.is_verified:
        return Response({
            'status': 'success',
            'message': 'Your email is already verified. You can log in.'
        }, status=status.HTTP_200_OK)
        
    otp = OTPCode.objects.filter(
        user=user,
        code=code,
        code_type='email_verification',
        is_used=False
    ).order_by('-created_at').first()
    
    if not otp or otp.is_expired():
        return Response({
            'status': 'error',
            'detail': 'Invalid or expired email verification code.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Mark user as verified and mark OTP as used
    user.is_verified = True
    user.save()
    
    otp.is_used = True
    otp.save()
    
    return Response({
        'status': 'success',
        'message': 'Email verified successfully! You can now log in.'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=ForgotPasswordSerializer,
    responses={
        200: 'Success - Reset OTP generated & dispatched if account exists'
    },
    operation_description="Requests a password reset code. Generates and sends a 6-digit OTP via ZeptoMail if email exists."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    Forgot Password request. Sends an OTP code for password reset.
    """
    serializer = ForgotPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    email = serializer.validated_data['email']
    
    try:
        user = User.objects.get(email=email)
        # Generate Password Reset OTP
        otp_code = get_random_string(length=6, allowed_chars='0123456789')
        OTPCode.objects.create(user=user, code=otp_code, code_type='password_reset')
        
        # Send Email via ZeptoMail SMTP with HTML template
        subject = 'Aishtop Salon - Reset Password'
        context = {
            'full_name': user.full_name,
            'otp_code': otp_code
        }
        try:
            html_content = render_to_string('emails/password_reset.html', context)
            text_content = strip_tags(html_content)
            
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email]
            )
            msg.attach_alternative(html_content, "text/html")
            send_email_async(msg)
        except Exception as e:
            pass
            
    except User.DoesNotExist:
        # Prevent email enumeration: return the same response even if user doesn't exist
        pass
        
    return Response({
        'status': 'success',
        'message': 'If an account exists with this email, a 6-digit password reset code has been sent.'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=ResetPasswordSerializer,
    responses={
        200: 'Success - Password updated successfully',
        400: 'Bad Request - Validation or expired OTP',
        404: 'Not Found - User not found'
    },
    operation_description="Resets the password using a valid 6-digit password reset OTP code received via email."
)
@api_view(['POST'])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Reset password using a valid OTP code.
    """
    serializer = ResetPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    email = serializer.validated_data['email']
    code = serializer.validated_data['code']
    new_password = serializer.validated_data['new_password']
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({
            'status': 'error',
            'detail': 'User account with this email does not exist.'
        }, status=status.HTTP_404_NOT_FOUND)
        
    otp = OTPCode.objects.filter(
        user=user,
        code=code,
        code_type='password_reset',
        is_used=False
    ).order_by('-created_at').first()
    
    if not otp or otp.is_expired():
        return Response({
            'status': 'error',
            'detail': 'Invalid or expired password reset code.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    # Update Password and mark OTP as used
    user.set_password(new_password)
    user.save()
    
    otp.is_used = True
    otp.save()
    
    return Response({
        'status': 'success',
        'message': 'Password has been reset successfully! You can now log in with your new password.'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='post',
    request_body=ChangePasswordSerializer,
    responses={
        200: 'Success - Password changed successfully',
        400: 'Bad Request - Invalid old password or validation errors',
        401: 'Unauthorized - Missing valid JWT token'
    },
    operation_description="Allows authenticated users to change their password by validating the old one."
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password (requires authentication).
    """
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({
            'status': 'error',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
        
    user = request.user
    old_password = serializer.validated_data['old_password']
    new_password = serializer.validated_data['new_password']
    
    if not user.check_password(old_password):
        return Response({
            'status': 'error',
            'detail': 'Your current password was entered incorrectly.'
        }, status=status.HTTP_400_BAD_REQUEST)
        
    user.set_password(new_password)
    user.save()
    
    return Response({
        'status': 'success',
        'message': 'Password changed successfully.'
    }, status=status.HTTP_200_OK)


@swagger_auto_schema(
    method='get',
    responses={
        200: UserSerializer(),
        401: 'Unauthorized - Invalid or missing token'
    },
    operation_description="Retrieves the current logged in user's profile details."
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_profile(request):
    """
    Retrieve the logged-in user's profile.
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data, status=status.HTTP_200_OK)
