"""
Identity URL Configuration
============================
Authentication API routes.

Endpoints:
    POST /api/send-otp/    — Step 1: Firebase sends OTP SMS; returns verification_token.
    POST /api/verify-otp/  — Step 2: Verify OTP → auto register or login (unified).
    POST /api/register/    — Step 2a (legacy): Verify OTP + register new user only.
    POST /api/login/       — Step 2b (legacy): Verify OTP + login existing user only.
    POST /api/admin/login/ — Email + password login for staff/superuser accounts.
"""

from django.urls import path
from .views import (
    SendOTPView,
    VerifyOTPView,
    RegisterView,
    LoginView,
    admin_login,
    AdminMePermissionsView,
    IncomePlusRequestCreateView,
    IncomePlusSendInviteView,
    IncomePlusValidateTokenView,
    IncomePlusOnboardingStatusView,
    IncomePlusStep1View,
    IncomePlusStep2View,
    IncomePlusStep3View,
    IncomePlusAdminRequestsView,
    IncomePlusAdminVerifyView,
)
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
import json

# Temporary OTP endpoint for development/testing
@csrf_exempt
def get_temp_otp(request):
    """Fetch the actual OTP from cache that was sent via send_otp"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone_number = data.get('phone_number', '')
            
            if not phone_number:
                return JsonResponse({'error': 'Phone number is required'}, status=400)
            
            # Search through all cache keys to find the OTP for this phone number
            # This is a bit inefficient but works for development/testing
            cache_prefix = "local_otp"
            
            # Try to find the OTP in cache by iterating through possible session keys
            # Since we can't easily list all cache keys, we'll check recent ones
            # This is a simplified approach for development
            
            # Alternative approach: check if there's a recent OTP request
            # We'll look for any cached OTP data for this phone number
            found_otp = None
            found_session = None
            
            # Since Django cache doesn't provide a way to list keys easily,
            # we'll use a different approach - store phone->session mapping
            phone_session_key = f"phone_session:{phone_number}"
            recent_session = cache.get(phone_session_key)
            
            if recent_session:
                cache_key = f"{cache_prefix}:{recent_session}"
                payload = cache.get(cache_key)
                if payload and payload.get('phone_number') == phone_number:
                    found_otp = payload.get('otp')
                    found_session = recent_session
            
            if found_otp:
                return JsonResponse({
                    'success': True,
                    'otp': found_otp,
                    'phone_number': phone_number,
                    'message': f'OTP for {phone_number} is: {found_otp}',
                    'session_info': found_session,
                    'expires_in': 300  # 5 minutes
                })
            else:
                return JsonResponse({
                    'error': 'No OTP found for this phone number. Please send OTP first.',
                    'message': 'Make sure to click "Send OTP" before trying to fetch it.'
                }, status=404)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

app_name = "identity"

urlpatterns = [
    # Step 1 — Request OTP via Firebase (call before verify-otp / register / login)
    path("send-otp/", SendOTPView.as_view(), name="send_otp"),

    # Temporary OTP endpoint for development/testing
    path("get-otp/", get_temp_otp, name="get_temp_otp"),

    # Step 2 — Verify OTP + auto register or login (preferred unified endpoint)
    path("verify-otp/", VerifyOTPView.as_view(), name="verify_otp"),

    # Step 2a (legacy) — Verify OTP + register new user
    path("register/", RegisterView.as_view(), name="register"),

    # Step 2b (legacy) — Verify OTP + login existing user
    path("login/", LoginView.as_view(), name="login"),

    # Admin — Email + password login (staff/superuser only)
    path("admin/login/", csrf_exempt(admin_login), name="admin_login"),

    # Admin — Current authenticated user's role/permission payload
    path("admin/me/permissions/", AdminMePermissionsView.as_view(), name="admin_me_permissions"),

    # IncomePlus onboarding (separate 3-step flow)
    path("incomeplus/onboarding/request/", IncomePlusRequestCreateView.as_view(), name="incomeplus_request_create"),
    path("incomeplus/onboarding/<int:pk>/send-link/", IncomePlusSendInviteView.as_view(), name="incomeplus_send_link"),
    path("incomeplus/onboarding/validate-token/", IncomePlusValidateTokenView.as_view(), name="incomeplus_validate_token"),
    path("incomeplus/onboarding/status/", IncomePlusOnboardingStatusView.as_view(), name="incomeplus_onboarding_status"),
    path("incomeplus/onboarding/step1/", IncomePlusStep1View.as_view(), name="incomeplus_step1"),
    path("incomeplus/onboarding/step2/", IncomePlusStep2View.as_view(), name="incomeplus_step2"),
    path("incomeplus/onboarding/step3/", IncomePlusStep3View.as_view(), name="incomeplus_step3"),
    path("incomeplus/onboarding/admin/requests/", IncomePlusAdminRequestsView.as_view(), name="incomeplus_admin_requests"),
    path("incomeplus/onboarding/admin/verify/<uuid:public_id>/", IncomePlusAdminVerifyView.as_view(), name="incomeplus_admin_verify"),
]
