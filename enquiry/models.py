from django.db import models
from django.contrib.auth.models import User as AuthUser
from identity.models import User
from categories.models import Product, ProductVariant
import uuid


# ============================================================================
# ENUMS
# ============================================================================

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


class BusinessType(models.TextChoices):
    SCHOOL = 'school', 'School'
    COLLEGE = 'college', 'College'
    OFFICE = 'office', 'Office'
    RETAILER = 'retailer', 'Retailer'
    INDIVIDUAL = 'individual', 'Individual'


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
        AuthUser, null=True, blank=True,
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
        AuthUser, null=True, blank=True,
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


class ContactUs(models.Model):
    """Lightweight contact form submissions from the website."""

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    organisation = models.CharField(max_length=255, null=True, blank=True)
    category = models.CharField(max_length=150, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    message = models.TextField(null=True, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'enquiry_contact_us'
        verbose_name = 'Contact Us'
        verbose_name_plural = 'Contact Us'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"