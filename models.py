"""
Django Models for Supplica B2B/B2C E-Commerce Platform
Generated from: supplica_ecommerce_schema.sql

Apps / Modules suggested:
  - identity   → users, profiles, KYC, sessions, admin
  - catalogue  → categories, products, variants, attributes
  - pricing    → offers, volume discounts, B2B tiers
  - enquiry    → enquiries, items, status history
  - quotation  → quotations, items, revisions, negotiations
  - orders     → orders, items, status history, invoices
  - payment    → transactions, attempts, refunds, EMI
  - ads        → advertisement banners
  - analytics  → product views, search analytics, click tracking
  - core       → notifications, system settings

NOTE:
  - UUIDs are used as public_id (exposed in APIs); internal PKs remain BigAutoField.
  - PostgreSQL-specific fields (ArrayField, JSONField, GenericIPAddressField) require
    'django.contrib.postgres' in INSTALLED_APPS.
  - search_vector (SearchVectorField) requires 'django.contrib.postgres'.
  - Soft-delete pattern: deleted_at is nullable DateTimeField; filter with deleted_at__isnull=True.
"""

import uuid
from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import SearchVectorField


# ============================================================================
# ENUMS (used as TextChoices in Django)
# ============================================================================

class UserType(models.TextChoices):
    B2C = 'b2c', 'B2C'
    B2B = 'b2b', 'B2B'

class UserRole(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    ADMIN = 'admin', 'Admin'
    SALES = 'sales', 'Sales'
    SUPPORT = 'support', 'Support'
    FINANCE = 'finance', 'Finance'

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

class ProductStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'

class DiscountType(models.TextChoices):
    PERCENTAGE = 'percentage', 'Percentage'
    FIXED_AMOUNT = 'fixed_amount', 'Fixed Amount'

class PriceType(models.TextChoices):
    BASE = 'base', 'Base'
    B2B_TIER1 = 'b2b_tier1', 'B2B Tier 1'
    B2B_TIER2 = 'b2b_tier2', 'B2B Tier 2'
    B2B_TIER3 = 'b2b_tier3', 'B2B Tier 3'
    PROMOTIONAL = 'promotional', 'Promotional'

class EnquiryStatus(models.TextChoices):
    NEW = 'new', 'New'
    CONTACTED = 'contacted', 'Contacted'
    QUOTATION_SENT = 'quotation_sent', 'Quotation Sent'
    CONVERTED = 'converted', 'Converted'
    LOST = 'lost', 'Lost'

class EnquirySource(models.TextChoices):
    WEBSITE = 'website', 'Website'
    MOBILE_APP = 'mobile_app', 'Mobile App'
    PHONE = 'phone', 'Phone'
    EMAIL = 'email', 'Email'
    WALK_IN = 'walk_in', 'Walk In'

class QuotationStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    VIEWED = 'viewed', 'Viewed'
    REVISED = 'revised', 'Revised'
    ACCEPTED = 'accepted', 'Accepted'
    REJECTED = 'rejected', 'Rejected'
    EXPIRED = 'expired', 'Expired'

class RevisionType(models.TextChoices):
    PRICE_CHANGE = 'price_change', 'Price Change'
    QUANTITY_CHANGE = 'quantity_change', 'Quantity Change'
    ITEM_ADDED = 'item_added', 'Item Added'
    ITEM_REMOVED = 'item_removed', 'Item Removed'
    DISCOUNT_APPLIED = 'discount_applied', 'Discount Applied'

class OrderStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CONFIRMED = 'confirmed', 'Confirmed'
    PROCESSING = 'processing', 'Processing'
    SHIPPED = 'shipped', 'Shipped'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'
    REFUNDED = 'refunded', 'Refunded'

class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    INITIATED = 'initiated', 'Initiated'
    SUCCESS = 'success', 'Success'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'
    PARTIALLY_REFUNDED = 'partially_refunded', 'Partially Refunded'

class PaymentMethod(models.TextChoices):
    RAZORPAY_CARD = 'razorpay_card', 'Razorpay Card'
    RAZORPAY_UPI = 'razorpay_upi', 'Razorpay UPI'
    RAZORPAY_NETBANKING = 'razorpay_netbanking', 'Razorpay Net Banking'
    RAZORPAY_WALLET = 'razorpay_wallet', 'Razorpay Wallet'
    EMI = 'emi', 'EMI'
    COD = 'cod', 'Cash on Delivery'

class InvoiceStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    SENT = 'sent', 'Sent'
    PAID = 'paid', 'Paid'
    OVERDUE = 'overdue', 'Overdue'
    CANCELLED = 'cancelled', 'Cancelled'


# ============================================================================
# IDENTITY — User Management & Authentication
# ============================================================================

class User(models.Model):
    """
    Minimal user record created on first enquiry (frictionless registration).
    Either phone or email must be provided.
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
    first_enquiry_id = models.BigIntegerField(null=True, blank=True)  # soft reference to enquiry

    profile_completed = models.BooleanField(default=False)
    kyc_completed = models.BooleanField(default=False)

    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    login_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)  # soft delete

    class Meta:
        db_table = 'identity_user'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

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
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"Profile of {self.user}"


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
        verbose_name = 'Business Detail'
        verbose_name_plural = 'Business Details'

    def __str__(self):
        return self.business_name


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
        verbose_name = 'User Session'
        verbose_name_plural = 'User Sessions'

    def __str__(self):
        return f"Session of {self.user} ({self.device_type})"


class AdminUser(models.Model):
    """
    Admin/staff accounts with roles and granular permissions.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.SUPPORT)

    permissions = models.JSONField(null=True, blank=True)
    # e.g. {"can_verify_kyc": true, "can_edit_prices": false}
    department = models.CharField(max_length=100, null=True, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'identity_admin_user'
        verbose_name = 'Admin User'
        verbose_name_plural = 'Admin Users'

    def __str__(self):
        return f"{self.user} [{self.role}]"


# ============================================================================
# CATALOGUE — Products, Categories, Search
# ============================================================================

class Category(models.Model):
    """
    Multi-level product category hierarchy (root → child → grandchild).
    Uses a materialized path (e.g., '1.5.23') for fast ancestor queries.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)

    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='children'
    )
    level = models.IntegerField(default=0)  # 0=root, 1=child, 2=grandchild
    path = models.TextField(null=True, blank=True)  # materialized path e.g. '1.5.23'

    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    meta_keywords = models.TextField(null=True, blank=True)

    image_url = models.TextField(null=True, blank=True)
    icon_url = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    is_featured = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'catalogue_category'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Core product listing with full-text search support, inventory tracking,
    and SEO metadata.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=500)
    slug = models.SlugField(max_length=500)
    sku = models.CharField(max_length=100, unique=True)
    short_description = models.TextField(null=True, blank=True)
    long_description = models.TextField(null=True, blank=True)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name='products')
    subcategory = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='subcategory_products'
    )

    base_price = models.DecimalField(max_digits=15, decimal_places=2)
    mrp = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    cost_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    stock_quantity = models.IntegerField(default=0)
    min_order_quantity = models.IntegerField(default=1)
    max_order_quantity = models.IntegerField(null=True, blank=True)
    low_stock_threshold = models.IntegerField(default=10)

    brand = models.CharField(max_length=255, null=True, blank=True)
    manufacturer = models.CharField(max_length=255, null=True, blank=True)
    model_number = models.CharField(max_length=100, null=True, blank=True)
    hsn_code = models.CharField(max_length=20, null=True, blank=True)

    weight_grams = models.IntegerField(null=True, blank=True)
    dimensions_cm = models.CharField(max_length=50, null=True, blank=True)  # e.g. "10x20x30"

    meta_title = models.CharField(max_length=255, null=True, blank=True)
    meta_description = models.TextField(null=True, blank=True)
    meta_keywords = models.TextField(null=True, blank=True)

    # Full-text search (PostgreSQL tsvector — updated via signal/trigger)
    search_vector = SearchVectorField(null=True, blank=True)
    search_keywords = ArrayField(models.TextField(), null=True, blank=True)
    popularity_score = models.IntegerField(default=0)
    search_rank = models.IntegerField(default=0)

    product_status = models.CharField(max_length=20, choices=ProductStatus.choices, default=ProductStatus.DRAFT)
    is_featured = models.BooleanField(default=False)
    is_new_arrival = models.BooleanField(default=False)
    is_trending = models.BooleanField(default=False)

    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'catalogue_product'
        verbose_name = 'Product'
        verbose_name_plural = 'Products'

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """
    Product images with ordering. One image is marked as primary.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images')

    image_url = models.TextField()
    thumbnail_url = models.TextField(null=True, blank=True)
    display_order = models.IntegerField(default=0)
    is_primary = models.BooleanField(default=False)
    alt_text = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalogue_product_image'
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['display_order']

    def __str__(self):
        return f"Image for {self.product} (order: {self.display_order})"


class ProductVariant(models.Model):
    """
    SKU-level product variants (e.g., Red-Large, Blue-Small) with their own
    pricing adjustment and stock.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')

    variant_name = models.CharField(max_length=255, null=True, blank=True)  # e.g. "Red - Large"
    sku = models.CharField(max_length=100, unique=True)

    attributes = models.JSONField()  # e.g. {"color": "Red", "size": "Large"}

    price_adjustment = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    stock_quantity = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'catalogue_product_variant'
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'

    def __str__(self):
        return f"{self.product} — {self.variant_name or self.sku}"


class Attribute(models.Model):
    """
    Filterable/searchable attribute definitions (e.g., Color, Size, Material).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    display_order = models.IntegerField(default=0)

    is_filterable = models.BooleanField(default=True)
    is_searchable = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalogue_attribute'
        verbose_name = 'Attribute'
        verbose_name_plural = 'Attributes'

    def __str__(self):
        return self.name


class AttributeValue(models.Model):
    """
    Possible values for a given attribute (e.g., Color → Red, Blue, Green).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE, related_name='values')

    value = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    display_order = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'catalogue_attribute_value'
        unique_together = [('attribute', 'value')]
        verbose_name = 'Attribute Value'
        verbose_name_plural = 'Attribute Values'

    def __str__(self):
        return f"{self.attribute.name}: {self.value}"


class ProductAttribute(models.Model):
    """
    Many-to-many mapping between products and their attribute values.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_attributes')
    attribute = models.ForeignKey(Attribute, on_delete=models.CASCADE)
    attribute_value = models.ForeignKey(AttributeValue, on_delete=models.CASCADE)

    class Meta:
        db_table = 'catalogue_product_attribute'
        unique_together = [('product', 'attribute')]
        verbose_name = 'Product Attribute'
        verbose_name_plural = 'Product Attributes'

    def __str__(self):
        return f"{self.product} — {self.attribute}: {self.attribute_value}"


class SearchSuggestion(models.Model):
    """
    Pre-computed autocomplete keywords with performance metrics.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    keyword = models.CharField(max_length=255, unique=True)
    suggestion_type = models.CharField(max_length=50, null=True, blank=True)
    # e.g. 'category', 'product', 'brand'
    entity_id = models.BigIntegerField(null=True, blank=True)

    search_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)
    conversion_count = models.IntegerField(default=0)

    relevance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'catalogue_search_suggestion'
        verbose_name = 'Search Suggestion'
        verbose_name_plural = 'Search Suggestions'

    def __str__(self):
        return self.keyword


# ============================================================================
# PRICING — Offers, Discounts, Volume Pricing, B2B Tiers
# ============================================================================

class CategoryOffer(models.Model):
    """
    Promotional discounts applied at the category level.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='offers')

    offer_name = models.CharField(max_length=255)
    offer_description = models.TextField(null=True, blank=True)

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=15, decimal_places=2)

    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    min_order_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    min_quantity = models.IntegerField(null=True, blank=True)
    max_discount_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    applicable_for_user_type = models.CharField(
        max_length=10, choices=UserType.choices, null=True, blank=True
    )  # NULL = all user types

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_category_offer'
        verbose_name = 'Category Offer'
        verbose_name_plural = 'Category Offers'

    def __str__(self):
        return f"{self.offer_name} on {self.category}"


class ProductOffer(models.Model):
    """
    Promotional discounts applied at the individual product level.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='offers')

    offer_name = models.CharField(max_length=255)
    offer_description = models.TextField(null=True, blank=True)

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=15, decimal_places=2)

    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()

    min_quantity = models.IntegerField(null=True, blank=True)
    max_discount_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    applicable_for_user_type = models.CharField(
        max_length=10, choices=UserType.choices, null=True, blank=True
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_product_offer'
        verbose_name = 'Product Offer'
        verbose_name_plural = 'Product Offers'

    def __str__(self):
        return f"{self.offer_name} on {self.product}"


class VolumeDiscount(models.Model):
    """
    Quantity-based discounts for products or categories.
    Applies to either a product OR a category, not both.
    Supports "buy 100 get 5% off" or "buy 100 at ₹500 each" models.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.CASCADE, related_name='volume_discounts'
    )
    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.CASCADE, related_name='volume_discounts'
    )

    min_quantity = models.IntegerField()
    max_quantity = models.IntegerField(null=True, blank=True)

    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    fixed_unit_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    applicable_for_user_type = models.CharField(
        max_length=10, choices=UserType.choices, null=True, blank=True
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_volume_discount'
        verbose_name = 'Volume Discount'
        verbose_name_plural = 'Volume Discounts'

    def __str__(self):
        target = self.product or self.category
        return f"Volume discount on {target} (min qty: {self.min_quantity})"


class B2BPriceTier(models.Model):
    """
    Special tiered pricing for B2B customers based on business type or purchase volume.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='b2b_price_tiers')

    tier_name = models.CharField(max_length=100)  # 'tier1', 'tier2', 'tier3'
    tier_price = models.DecimalField(max_digits=15, decimal_places=2)

    min_annual_purchase = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    business_types = ArrayField(
        models.CharField(max_length=20, choices=BusinessType.choices),
        null=True, blank=True
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pricing_b2b_price_tier'
        verbose_name = 'B2B Price Tier'
        verbose_name_plural = 'B2B Price Tiers'

    def __str__(self):
        return f"{self.tier_name} — {self.product}"


class UserPriceTier(models.Model):
    """
    Assigns a B2B price tier to a specific user.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='price_tiers')
    tier_name = models.CharField(max_length=100)

    assigned_by = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_user_tiers'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'pricing_user_price_tier'
        unique_together = [('user', 'tier_name')]
        verbose_name = 'User Price Tier'
        verbose_name_plural = 'User Price Tiers'

    def __str__(self):
        return f"{self.user} — {self.tier_name}"


# ============================================================================
# ADS — Advertisement Banners
# ============================================================================

class AdvertisementBanner(models.Model):
    """
    Promotional banners shown on category pages, product pages, sidebars, etc.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    title = models.CharField(max_length=255)

    category = models.ForeignKey(
        Category, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ad_banners'
    )
    product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='ad_banners'
    )
    offer_id = models.BigIntegerField(null=True, blank=True)
    # soft reference to category_offers or product_offers

    banner_image_url = models.TextField()
    banner_mobile_image_url = models.TextField(null=True, blank=True)
    click_url = models.TextField(null=True, blank=True)

    display_position = models.CharField(max_length=50, null=True, blank=True)
    # e.g. 'top', 'sidebar', 'category_page', 'product_page'
    display_order = models.IntegerField(default=0)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField()

    impression_count = models.IntegerField(default=0)
    click_count = models.IntegerField(default=0)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'ads_advertisement_banner'
        verbose_name = 'Advertisement Banner'
        verbose_name_plural = 'Advertisement Banners'

    def __str__(self):
        return self.title


# ============================================================================
# ENQUIRY — Core Enquiry System
# ============================================================================

class Enquiry(models.Model):
    """
    Customer product enquiries. Auto-creates a User record in the background
    when submitted (handled via signal/service layer, mirroring the SQL trigger).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='enquiries'
    )

    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField(max_length=255, null=True, blank=True)
    customer_phone = models.CharField(max_length=20)

    company_name = models.CharField(max_length=255, null=True, blank=True)
    business_type = models.CharField(max_length=20, choices=BusinessType.choices, null=True, blank=True)

    enquiry_source = models.CharField(max_length=20, choices=EnquirySource.choices, default=EnquirySource.WEBSITE)
    enquiry_status = models.CharField(max_length=20, choices=EnquiryStatus.choices, default=EnquiryStatus.NEW)

    message = models.TextField(null=True, blank=True)
    preferred_delivery_date = models.DateField(null=True, blank=True)
    budget_range = models.CharField(max_length=50, null=True, blank=True)

    delivery_address = models.TextField(null=True, blank=True)
    delivery_city = models.CharField(max_length=100, null=True, blank=True)
    delivery_state = models.CharField(max_length=100, null=True, blank=True)
    delivery_pincode = models.CharField(max_length=10, null=True, blank=True)

    assigned_to_admin = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='assigned_enquiries'
    )
    assigned_at = models.DateTimeField(null=True, blank=True)

    converted_to_quotation_id = models.BigIntegerField(null=True, blank=True)
    converted_to_order_id = models.BigIntegerField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    admin_notes = models.TextField(null=True, blank=True)

    user_agent = models.TextField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    referrer_url = models.TextField(null=True, blank=True)
    utm_source = models.CharField(max_length=100, null=True, blank=True)
    utm_medium = models.CharField(max_length=100, null=True, blank=True)
    utm_campaign = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'enquiry_enquiry'
        verbose_name = 'Enquiry'
        verbose_name_plural = 'Enquiries'
        ordering = ['-created_at']

    def __str__(self):
        return f"Enquiry #{self.id} by {self.customer_name}"


class EnquiryItem(models.Model):
    """
    Line items inside an enquiry with product/pricing snapshot at enquiry time.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='enquiry_items')
    variant = models.ForeignKey(
        ProductVariant, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='enquiry_items'
    )

    # Snapshot at enquiry time
    product_name = models.CharField(max_length=500, null=True, blank=True)
    product_sku = models.CharField(max_length=100, null=True, blank=True)
    unit_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    quantity = models.IntegerField()
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'enquiry_item'
        verbose_name = 'Enquiry Item'
        verbose_name_plural = 'Enquiry Items'

    def __str__(self):
        return f"{self.product_name or self.product} x {self.quantity}"


class EnquiryStatusHistory(models.Model):
    """
    Audit log for every status change on an enquiry.
    """
    enquiry = models.ForeignKey(Enquiry, on_delete=models.CASCADE, related_name='status_history')

    from_status = models.CharField(max_length=20, choices=EnquiryStatus.choices, null=True, blank=True)
    to_status = models.CharField(max_length=20, choices=EnquiryStatus.choices)

    changed_by = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='enquiry_status_changes'
    )
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'enquiry_status_history'
        verbose_name = 'Enquiry Status History'
        verbose_name_plural = 'Enquiry Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"Enquiry #{self.enquiry_id}: {self.from_status} → {self.to_status}"


# ============================================================================
# QUOTATION — Quotation Engine with Revisions
# ============================================================================

class Quotation(models.Model):
    """
    Sales quotations created from enquiries. Supports multiple revisions
    and negotiation threads before acceptance.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    enquiry = models.ForeignKey(Enquiry, on_delete=models.PROTECT, related_name='quotations')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='quotations')

    quotation_number = models.CharField(max_length=100, unique=True)  # e.g. QT-2024-00001
    version = models.IntegerField(default=1)

    quotation_status = models.CharField(max_length=20, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT)

    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    shipping_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    valid_until = models.DateTimeField()

    payment_terms = models.TextField(null=True, blank=True)
    delivery_terms = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    converted_to_order_id = models.BigIntegerField(null=True, blank=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    created_by_admin = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='created_quotations'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'quotation_quotation'
        verbose_name = 'Quotation'
        verbose_name_plural = 'Quotations'
        ordering = ['-created_at']

    def __str__(self):
        return self.quotation_number


class QuotationItem(models.Model):
    """
    Line items in a quotation with individually negotiated prices and discounts.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='quotation_items')
    variant = models.ForeignKey(
        ProductVariant, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='quotation_items'
    )

    product_name = models.CharField(max_length=500)
    product_sku = models.CharField(max_length=100)

    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2)

    notes = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quotation_item'
        verbose_name = 'Quotation Item'
        verbose_name_plural = 'Quotation Items'

    def __str__(self):
        return f"{self.product_name} x {self.quantity} ({self.quotation})"


class QuotationRevision(models.Model):
    """
    Full audit trail of every change made to a quotation (price, qty, items).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='revisions')

    version = models.IntegerField()
    revision_type = models.CharField(max_length=20, choices=RevisionType.choices)

    previous_data = models.JSONField(null=True, blank=True)
    changes_made = models.JSONField(null=True, blank=True)
    # e.g. {"subtotal": {"old": 1000, "new": 900}}

    revision_reason = models.TextField(null=True, blank=True)
    revised_by = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='quotation_revisions'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quotation_revision'
        verbose_name = 'Quotation Revision'
        verbose_name_plural = 'Quotation Revisions'
        ordering = ['-version']

    def __str__(self):
        return f"{self.quotation} v{self.version} — {self.revision_type}"


class QuotationNegotiation(models.Model):
    """
    Threaded messages between customer and admin during quotation negotiation.
    Either sent_by_user or sent_by_admin must be set (not both).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    quotation = models.ForeignKey(Quotation, on_delete=models.CASCADE, related_name='negotiations')

    message = models.TextField()

    sent_by_user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='negotiation_messages'
    )
    sent_by_admin = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='negotiation_messages'
    )

    attachments = models.JSONField(null=True, blank=True)
    # e.g. [{"url": "...", "filename": "..."}]

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'quotation_negotiation'
        verbose_name = 'Quotation Negotiation'
        verbose_name_plural = 'Quotation Negotiations'
        ordering = ['created_at']

    def __str__(self):
        sender = self.sent_by_user or self.sent_by_admin
        return f"Message on {self.quotation} by {sender}"


# ============================================================================
# ORDERS — Order Management
# ============================================================================

class Order(models.Model):
    """
    Customer orders (direct or converted from quotation).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='orders')
    quotation = models.ForeignKey(
        Quotation, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='orders'
    )

    order_number = models.CharField(max_length=100, unique=True)  # e.g. ORD-2024-00001
    order_status = models.CharField(max_length=20, choices=OrderStatus.choices, default=OrderStatus.PENDING)

    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    shipping_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)

    delivery_address = models.TextField()
    delivery_city = models.CharField(max_length=100, null=True, blank=True)
    delivery_state = models.CharField(max_length=100, null=True, blank=True)
    delivery_pincode = models.CharField(max_length=10, null=True, blank=True)
    delivery_phone = models.CharField(max_length=20, null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)

    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, null=True, blank=True)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    customer_notes = models.TextField(null=True, blank=True)
    admin_notes = models.TextField(null=True, blank=True)

    placed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders_order'
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']

    def __str__(self):
        return self.order_number


class OrderItem(models.Model):
    """
    Line items in an order with price/discount/tax snapshot at order time.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='order_items')
    variant = models.ForeignKey(
        ProductVariant, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_items'
    )

    product_name = models.CharField(max_length=500)
    product_sku = models.CharField(max_length=100)

    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=15, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=15, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders_order_item'
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.product_name} x {self.quantity} ({self.order})"


class OrderStatusHistory(models.Model):
    """
    Audit log for every status transition on an order.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')

    from_status = models.CharField(max_length=20, choices=OrderStatus.choices, null=True, blank=True)
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)

    notes = models.TextField(null=True, blank=True)
    changed_by = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='order_status_changes'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'orders_status_history'
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"Order #{self.order_id}: {self.from_status} → {self.to_status}"


class Invoice(models.Model):
    """
    GST invoices generated for orders. Tracks paid/balance amounts and PDF link.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='invoices')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='invoices')

    invoice_number = models.CharField(max_length=100, unique=True)  # e.g. INV-2024-00001
    invoice_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=15, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=15, decimal_places=2)
    shipping_charges = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=15, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    balance_amount = models.DecimalField(max_digits=15, decimal_places=2)

    invoice_status = models.CharField(max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT)
    invoice_pdf_url = models.TextField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders_invoice'
        verbose_name = 'Invoice'
        verbose_name_plural = 'Invoices'

    def __str__(self):
        return self.invoice_number


# ============================================================================
# PAYMENT — Razorpay Integration, Attempts, Refunds, EMI
# ============================================================================

class PaymentTransaction(models.Model):
    """
    Payment records linked to Razorpay. NEVER trust frontend status —
    always verify with Razorpay webhook/API.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payment_transactions')
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='payment_transactions')

    razorpay_order_id = models.CharField(max_length=100, unique=True, null=True, blank=True)
    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    razorpay_signature = models.CharField(max_length=255, null=True, blank=True)

    amount = models.DecimalField(max_digits=15, decimal_places=2)
    currency = models.CharField(max_length=3, default='INR')

    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices)
    payment_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    is_emi = models.BooleanField(default=False)
    emi_plan_id = models.CharField(max_length=100, null=True, blank=True)
    emi_duration_months = models.IntegerField(null=True, blank=True)
    emi_amount_per_month = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    emi_interest_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    gateway_response = models.JSONField(null=True, blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_description = models.TextField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_transaction'
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    def __str__(self):
        return f"Payment {self.razorpay_payment_id or self.pk} — {self.payment_status}"


class PaymentAttempt(models.Model):
    """
    Individual payment attempts for a transaction (retry tracking).
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    payment_transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.CASCADE, related_name='attempts'
    )

    attempt_number = models.IntegerField()
    payment_method = models.CharField(max_length=30, choices=PaymentMethod.choices, null=True, blank=True)

    razorpay_payment_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=PaymentStatus.choices, null=True, blank=True)

    error_code = models.CharField(max_length=50, null=True, blank=True)
    error_description = models.TextField(null=True, blank=True)
    gateway_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_attempt'
        verbose_name = 'Payment Attempt'
        verbose_name_plural = 'Payment Attempts'

    def __str__(self):
        return f"Attempt #{self.attempt_number} for txn {self.payment_transaction_id}"


class Refund(models.Model):
    """
    Refund requests and their processing status via Razorpay.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    payment_transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.PROTECT, related_name='refunds'
    )
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='refunds')

    refund_amount = models.DecimalField(max_digits=15, decimal_places=2)
    refund_reason = models.TextField(null=True, blank=True)

    razorpay_refund_id = models.CharField(max_length=100, null=True, blank=True)
    refund_status = models.CharField(max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING)

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'payment_refund'
        verbose_name = 'Refund'
        verbose_name_plural = 'Refunds'

    def __str__(self):
        return f"Refund ₹{self.refund_amount} for order {self.order}"


class EMIPlan(models.Model):
    """
    Available Razorpay EMI plans offered at checkout.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    plan_name = models.CharField(max_length=255)
    duration_months = models.IntegerField()
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    min_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    bank_name = models.CharField(max_length=255, null=True, blank=True)
    card_type = models.CharField(max_length=50, null=True, blank=True)  # 'credit', 'debit'

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_emi_plan'
        verbose_name = 'EMI Plan'
        verbose_name_plural = 'EMI Plans'

    def __str__(self):
        return f"{self.plan_name} ({self.duration_months} months @ {self.interest_rate}%)"


# ============================================================================
# ANALYTICS — User Behaviour & Tracking
# ============================================================================

class ProductView(models.Model):
    """
    Tracks every product page view. High-volume table — partition by month in production.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='views')
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='product_views'
    )
    session_id = models.UUIDField(null=True, blank=True)

    referrer_url = models.TextField(null=True, blank=True)
    search_query = models.CharField(max_length=500, null=True, blank=True)

    device_type = models.CharField(max_length=50, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_product_view'
        verbose_name = 'Product View'
        verbose_name_plural = 'Product Views'

    def __str__(self):
        return f"View on {self.product} at {self.viewed_at}"


class SearchAnalytic(models.Model):
    """
    Tracks search queries, click-through rates, and enquiry conversion from search.
    """
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='search_analytics'
    )
    session_id = models.UUIDField(null=True, blank=True)

    search_query = models.CharField(max_length=500)
    search_results_count = models.IntegerField(default=0)

    clicked_product = models.ForeignKey(
        Product, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='search_clicks'
    )
    clicked_position = models.IntegerField(null=True, blank=True)

    led_to_enquiry = models.BooleanField(default=False)
    enquiry_id = models.BigIntegerField(null=True, blank=True)

    device_type = models.CharField(max_length=50, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    searched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_search_analytic'
        verbose_name = 'Search Analytic'
        verbose_name_plural = 'Search Analytics'

    def __str__(self):
        return f"Search: '{self.search_query}' at {self.searched_at}"


class RecentlyViewedProduct(models.Model):
    """
    Per-user recently viewed product list (deduplicated, with view count).
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recently_viewed')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='recent_viewers')

    last_viewed_at = models.DateTimeField(auto_now=True)
    view_count = models.IntegerField(default=1)

    class Meta:
        db_table = 'analytics_recently_viewed_product'
        unique_together = [('user', 'product')]
        verbose_name = 'Recently Viewed Product'
        verbose_name_plural = 'Recently Viewed Products'

    def __str__(self):
        return f"{self.user} viewed {self.product}"


class ClickTracking(models.Model):
    """
    Generic click event tracker for ads, offers, and product cards.
    """
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='click_events'
    )
    session_id = models.UUIDField(null=True, blank=True)

    click_type = models.CharField(max_length=100)
    # e.g. 'ad_banner', 'category_offer', 'product_card'
    entity_id = models.BigIntegerField(null=True, blank=True)

    click_url = models.TextField(null=True, blank=True)
    referrer_url = models.TextField(null=True, blank=True)

    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'analytics_click_tracking'
        verbose_name = 'Click Tracking'
        verbose_name_plural = 'Click Trackings'

    def __str__(self):
        return f"Click [{self.click_type}] entity={self.entity_id} at {self.clicked_at}"


# ============================================================================
# CORE / UTILITY
# ============================================================================

class Notification(models.Model):
    """
    In-app, email, SMS, and push notifications for users.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User, null=True, blank=True,
        on_delete=models.CASCADE, related_name='notifications'
    )

    notification_type = models.CharField(max_length=100)
    # e.g. 'enquiry_received', 'quotation_sent', 'order_confirmed'
    title = models.CharField(max_length=255)
    message = models.TextField()

    action_url = models.TextField(null=True, blank=True)

    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    sent_via = ArrayField(models.CharField(max_length=20), null=True, blank=True)
    # e.g. ['email', 'sms', 'push', 'in_app']

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_notification'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.notification_type}] {self.title} → {self.user}"


class SystemSetting(models.Model):
    """
    Key-value configuration store for platform settings (GST %, shipping, etc.).
    """
    setting_key = models.CharField(max_length=100, unique=True)
    setting_value = models.TextField(null=True, blank=True)
    setting_type = models.CharField(max_length=50, default='string')
    # e.g. 'string', 'number', 'boolean', 'json'
    description = models.TextField(null=True, blank=True)

    updated_by = models.ForeignKey(
        AdminUser, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='updated_settings'
    )
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'core_system_setting'
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f"{self.setting_key} = {self.setting_value}"
