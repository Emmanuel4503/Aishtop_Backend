from django.urls import path
from .views import (
    register_user,
    login_user,
    refresh_token,
    get_user_profile,
    verify_email,
    forgot_password,
    reset_password,
    change_password
)

urlpatterns = [
    path('register/', register_user, name='auth_register'),
    path('verify-email/', verify_email, name='auth_verify_email'),
    path('login/', login_user, name='auth_login'),
    path('refresh/', refresh_token, name='auth_refresh'),
    path('profile/', get_user_profile, name='auth_profile'),
    path('forgot-password/', forgot_password, name='auth_forgot_password'),
    path('reset-password/', reset_password, name='auth_reset_password'),
    path('change-password/', change_password, name='auth_change_password'),
]
