"""
Identity Serializers
=====================
Input validation for all authentication endpoints.

Serializers:
    SendOTPSerializer    — validates phone_number (E.164) + optional recaptcha_token
    VerifyOTPSerializer  — validates phone_number, otp, and verification_token
"""

import re
from rest_framework import serializers

_E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")
_OTP_PATTERN = re.compile(r"^\d{6}$")


def _validate_e164(value: str) -> str:
    """Validate and return a phone number in E.164 format (e.g. +91XXXXXXXXXX)."""
    value = value.strip()
    if not _E164_PATTERN.match(value):
        raise serializers.ValidationError(
            "Invalid phone number. Use E.164 format (e.g. +91XXXXXXXXXX)."
        )
    return value


# ============================================================================
# SEND OTP SERIALIZER
# ============================================================================

class SendOTPSerializer(serializers.Serializer):
    """
    Validates the send-otp request payload.
    Used by: POST /api/send-otp/

    Fields:
        phone_number    — Required. International E.164 format (+91XXXXXXXXXX).
        recaptcha_token — Optional. reCAPTCHA token from Firebase Web SDK
                          RecaptchaVerifier. Required for production; bypassed
                          automatically for Firebase test phone numbers.
    """

    phone_number = serializers.CharField(
        required=True,
        max_length=15,
        help_text="Phone number in E.164 format (e.g. +91XXXXXXXXXX)",
    )
    recaptcha_token = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text=(
            "reCAPTCHA token from Firebase Web SDK RecaptchaVerifier. "
            "Required for production; not needed for Firebase test phone numbers."
        ),
    )

    def validate_phone_number(self, value: str) -> str:
        return _validate_e164(value)


# ============================================================================
# VERIFY OTP SERIALIZER
# ============================================================================

class VerifyOTPSerializer(serializers.Serializer):
    """
    Validates the verify-otp request payload.
    Used by: POST /api/verify-otp/  (unified register + login)
             POST /api/register/    (legacy — register only)
             POST /api/login/       (legacy — login only)

    Fields:
        phone_number       — Required. E.164 format (+91XXXXXXXXXX).
        otp                — Required. 6-digit OTP received via SMS.
        verification_token — Required. session_info token returned by /api/send-otp/.
    """

    phone_number = serializers.CharField(
        required=True,
        max_length=15,
        help_text="Phone number in E.164 format (e.g. +91XXXXXXXXXX)",
    )
    otp = serializers.CharField(
        required=True,
        min_length=6,
        max_length=6,
        help_text="6-digit OTP received via SMS",
    )
    verification_token = serializers.CharField(
        required=True,
        help_text="session_info token returned by the /api/send-otp/ endpoint",
    )

    def validate_phone_number(self, value: str) -> str:
        return _validate_e164(value)

    def validate_otp(self, value: str) -> str:
        value = value.strip()
        if not _OTP_PATTERN.match(value):
            raise serializers.ValidationError("Invalid OTP. Must be exactly 6 digits.")
        return value


# ============================================================================
# ROLE MANAGEMENT SERIALIZERS
# ============================================================================

class PermissionSerializer(serializers.Serializer):
    """Read-only representation of a Django auth.Permission."""
    id = serializers.IntegerField()
    name = serializers.CharField()
    codename = serializers.CharField()
    app_label = serializers.SerializerMethodField()

    def get_app_label(self, obj):
        return obj.content_type.app_label


class RoleSerializer(serializers.Serializer):
    """Serializes a Role with its permissions."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    permissions = PermissionSerializer(many=True, read_only=True)


class RoleWriteSerializer(serializers.Serializer):
    """Validates create/update payloads for Role."""
    name = serializers.CharField(max_length=100)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    permissions = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
    )


class AdminUserWriteSerializer(serializers.Serializer):
    """Validates create/update payloads for auth_user (admin users)."""
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True, default='')
    password = serializers.CharField(required=False, allow_blank=True, default='')
    first_name = serializers.CharField(required=False, allow_blank=True, default='')
    last_name = serializers.CharField(required=False, allow_blank=True, default='')
    is_staff = serializers.BooleanField(required=False, default=False)
    is_active = serializers.BooleanField(required=False, default=True)
    groups = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        default=list,
        help_text='List of Role IDs to assign',
    )


class IncomePlusRequestCreateSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=20)
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')


class IncomePlusStep1Serializer(serializers.Serializer):
    token = serializers.UUIDField()
    full_name = serializers.CharField(max_length=255)
    email = serializers.EmailField(max_length=255)
    phone = serializers.CharField(max_length=20)
    company_name = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    password = serializers.CharField(min_length=6, max_length=128)
    confirm_password = serializers.CharField(min_length=6, max_length=128)

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class IncomePlusStep2Serializer(serializers.Serializer):
    token = serializers.UUIDField()
    bank_account_holder = serializers.CharField(max_length=255)
    bank_name = serializers.CharField(max_length=255)
    bank_account_number = serializers.CharField(max_length=50)
    bank_ifsc = serializers.CharField(max_length=20)
    bank_branch = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    upi_id = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')


class IncomePlusStep3Serializer(serializers.Serializer):
    token = serializers.UUIDField()
    pan_number = serializers.CharField(max_length=20)
    gst_number = serializers.CharField(max_length=30, required=False, allow_blank=True, default='')
    aadhar_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default='')
    pan_document_url = serializers.CharField(required=False, allow_blank=True, default='')
    gst_document_url = serializers.CharField(required=False, allow_blank=True, default='')
    aadhar_document_url = serializers.CharField(required=False, allow_blank=True, default='')


class IncomePlusAdminVerifySerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['approve', 'reject'])
    admin_notes = serializers.CharField(required=False, allow_blank=True, default='')
