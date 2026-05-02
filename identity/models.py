"""
Identity Models
================
Models mapped to the existing identity_user table.
No migrations should alter the database schema.
"""

import uuid
from django.contrib.auth.models import User as AuthUser
from django.db import models


# ============================================================================
# ENUMS (TextChoices used by identity models)
# ============================================================================

class UserType(models.TextChoices):
    B2C = 'b2c', 'B2C'
    B2B = 'b2b', 'B2B'


class AccountStatus(models.TextChoices):
    INCOMPLETE = 'incomplete', 'Incomplete'
    ACTIVE = 'active', 'Active'
    SUSPENDED = 'suspended', 'Suspended'
    DEACTIVATED = 'deactivated', 'Deactivated'


class KYCStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    PENDING = 'pending', 'Pending'
    VERIFIED = 'verified', 'Verified'
    REJECTED = 'rejected', 'Rejected'


class BusinessType(models.TextChoices):
    SCHOOL = 'school', 'School'
    COLLEGE = 'college', 'College'
    OFFICE = 'office', 'Office'
    RETAILER = 'retailer', 'Retailer'
    INDIVIDUAL = 'individual', 'Individual'


# ============================================================================
# USER — Single model for identity_user table
# ============================================================================

class User(models.Model):
    """
    User record mapped to the existing 'identity_user' table.
    Used for authentication (register / login) via phone + OTP.

    The 'phone' field is used for mobile number storage.
    Other fields remain untouched during auth and get populated
    later when the user fills in profile details from the UI.
    """

    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    full_name = models.CharField(max_length=255, null=True, blank=True)

    password_hash = models.CharField(max_length=255, null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)

    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.B2C)
    account_status = models.CharField(max_length=20, choices=AccountStatus.choices, default=AccountStatus.INCOMPLETE)

    created_from_enquiry = models.BooleanField(default=False)
    first_enquiry_id = models.BigIntegerField(null=True, blank=True)

    profile_completed = models.BooleanField(default=False)
    kyc_completed = models.BooleanField(default=False)

    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'identity_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        managed = True  # <-- Add this (or remove managed line entirely)


    def __str__(self):
        return self.full_name or self.email or self.phone or str(self.public_id)
    

class UserProfile(models.Model):
    """
    Extended profile details filled after initial registration.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')

    first_name = models.CharField(max_length=100, null=True, blank=True)
    last_name = models.CharField(max_length=100, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, null=True, blank=True)

    address_line1 = models.TextField(null=True, blank=True)
    address_line2 = models.TextField(null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    pincode = models.CharField(max_length=10, null=True, blank=True)
    country = models.CharField(max_length=100, default='India')

    alternate_phone = models.CharField(max_length=20, null=True, blank=True)
    whatsapp_number = models.CharField(max_length=20, null=True, blank=True)

    preferred_language = models.CharField(max_length=10, default='en')
    communication_preferences = models.JSONField(null=True, blank=True)
    # e.g. {"email": true, "sms": true, "whatsapp": false}

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_user_profile'
        managed = True  # <-- Change from False to True
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'


    def __str__(self):
        return f"Profile of {self.user}"
    

class KYCDocument(models.Model):
    """
    KYC verification documents uploaded by users (Aadhar, PAN, GST, etc.).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='kyc_documents')

    document_type = models.CharField(max_length=50)
    # e.g. 'aadhar', 'pan', 'gst_certificate', 'business_proof'
    document_number = models.CharField(max_length=100, null=True, blank=True)
    document_url = models.TextField()
    document_back_url = models.TextField(null=True, blank=True)  # for Aadhar back

    kyc_status = models.CharField(max_length=20, choices=KYCStatus.choices, default=KYCStatus.PENDING)
    verified_by = models.BigIntegerField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_kyc_document'
        managed = True  # <-- Change from False to True
        verbose_name = 'KYC Document'
        verbose_name_plural = 'KYC Documents'


    def __str__(self):
        return f"{self.document_type} – {self.user}"
    

class OTPVerification(models.Model):
    """
    OTP codes for phone/email verification and login.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    otp_code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=50)
    # e.g. 'login', 'registration', 'phone_verify', 'email_verify'

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'identity_otp_verification'
        managed = True  # <-- Change from False to True
        verbose_name = 'OTP Verification'
        verbose_name_plural = 'OTP Verifications'


    def __str__(self):
        return f"OTP [{self.purpose}] for {self.phone or self.email}"


class UserSession(models.Model):
    """
    Active user sessions tracked per device.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')

    session_token = models.CharField(max_length=255, unique=True)
    device_id = models.CharField(max_length=255, null=True, blank=True)
    device_type = models.CharField(max_length=50, null=True, blank=True)
    # e.g. 'web', 'mobile_android', 'mobile_ios'
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'identity_user_session'
        managed = True  # <-- Change from False to True
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'


    def __str__(self):
        return f"Session of {self.user} ({self.device_type})"
    

class BusinessDetail(models.Model):
    """
    Business information for B2B customers (schools, colleges, offices, etc.).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='business_detail')

    business_name = models.CharField(max_length=255)
    business_type = models.CharField(max_length=20, choices=BusinessType.choices)
    registration_number = models.CharField(max_length=100, null=True, blank=True)
    gst_number = models.CharField(max_length=15, null=True, blank=True)
    pan_number = models.CharField(max_length=10, null=True, blank=True)

    business_address = models.TextField(null=True, blank=True)
    business_city = models.CharField(max_length=100, null=True, blank=True)
    business_state = models.CharField(max_length=100, null=True, blank=True)
    business_pincode = models.CharField(max_length=10, null=True, blank=True)

    contact_person_name = models.CharField(max_length=255, null=True, blank=True)
    contact_person_designation = models.CharField(max_length=100, null=True, blank=True)
    contact_person_phone = models.CharField(max_length=20, null=True, blank=True)
    contact_person_email = models.EmailField(max_length=255, null=True, blank=True)

    website_url = models.URLField(null=True, blank=True)
    established_year = models.IntegerField(null=True, blank=True)
    employee_count = models.IntegerField(null=True, blank=True)
    annual_turnover = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.BigIntegerField(null=True, blank=True)  # admin user id

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_business_detail'
        managed = True  # <-- Change from False to True
        verbose_name = 'Business Detail'
        verbose_name_plural = 'Business Details'

    def __str__(self):
        return self.business_name


# ============================================================================
# ROLE — Custom role with Django auth permissions
# ============================================================================

class Role(models.Model):
    """
    Custom roles that link to Django's built-in auth.Permission.
    Each role is synced to a Django Group so that standard
    permission checks (user.has_perm) work automatically.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, default='')
    permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='identity_roles',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_role'
        managed = True
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name


class IncomePlusOnboardingStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    INVITED = 'invited', 'Invited'
    IN_PROGRESS = 'in_progress', 'In Progress'
    PENDING_APPROVAL = 'pending_approval', 'Pending Approval'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'


class IncomePlusOnboardingRequest(models.Model):
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    invite_token = models.UUIDField(unique=True, null=True, blank=True)

    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True)
    phone = models.CharField(max_length=20)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    designation = models.CharField(max_length=100, null=True, blank=True)

    bank_account_holder = models.CharField(max_length=255, null=True, blank=True)
    bank_name = models.CharField(max_length=255, null=True, blank=True)
    bank_account_number = models.CharField(max_length=50, null=True, blank=True)
    bank_ifsc = models.CharField(max_length=20, null=True, blank=True)
    bank_branch = models.CharField(max_length=255, null=True, blank=True)
    upi_id = models.CharField(max_length=100, null=True, blank=True)

    pan_number = models.CharField(max_length=20, null=True, blank=True)
    gst_number = models.CharField(max_length=30, null=True, blank=True)
    aadhar_number = models.CharField(max_length=20, null=True, blank=True)
    pan_document_url = models.TextField(null=True, blank=True)
    gst_document_url = models.TextField(null=True, blank=True)
    aadhar_document_url = models.TextField(null=True, blank=True)

    current_step = models.PositiveSmallIntegerField(default=1)
    step1_completed = models.BooleanField(default=False)
    step2_completed = models.BooleanField(default=False)
    step3_completed = models.BooleanField(default=False)

    status = models.CharField(
        max_length=30,
        choices=IncomePlusOnboardingStatus.choices,
        default=IncomePlusOnboardingStatus.REQUESTED,
    )
    admin_notes = models.TextField(null=True, blank=True)
    invite_sent_at = models.DateTimeField(null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    linked_admin_user = models.ForeignKey(
        AuthUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='incomeplus_onboarding_profiles',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_incomeplus_onboarding_request'
        managed = True
        verbose_name = 'IncomePlus Onboarding Request'
        verbose_name_plural = 'IncomePlus Onboarding Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.full_name} ({self.email})"