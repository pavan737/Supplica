"""
Enquiry Serializers
====================
Validation and representation for Enquiry, EnquiryItem, and EnquiryStatusHistory.
"""

from rest_framework import serializers

from .models import (
    Enquiry,
    EnquiryItem,
    EnquiryStatusHistory,
    ContactUs,
    EnquirySource,
    EnquiryStatus,
    BusinessType,
)


# ============================================================================
# READ serializers (used in list / detail responses)
# ============================================================================

class EnquiryItemReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source='product.id', read_only=True)
    variant_id = serializers.SerializerMethodField()

    class Meta:
        model = EnquiryItem
        fields = [
            'id', 'public_id',
            'product_id', 'variant_id',
            'product_name', 'product_sku', 'unit_price',
            'quantity', 'notes',
            'created_at',
        ]

    def get_variant_id(self, obj):
        return obj.variant_id if obj.variant_id else None


class EnquiryStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = EnquiryStatusHistory
        fields = [
            'id', 'from_status', 'to_status',
            'changed_by', 'changed_by_username',
            'notes', 'created_at',
        ]

    def get_changed_by_username(self, obj):
        if obj.changed_by:
            return obj.changed_by.username
        return None


class EnquiryReadSerializer(serializers.ModelSerializer):
    items = EnquiryItemReadSerializer(many=True, read_only=True)
    status_history = EnquiryStatusHistorySerializer(many=True, read_only=True)
    user_id = serializers.SerializerMethodField()
    assigned_to_admin_username = serializers.SerializerMethodField()

    class Meta:
        model = Enquiry
        fields = [
            'id', 'public_id',
            'user_id',
            'customer_name', 'customer_email', 'customer_phone',
            'company_name', 'business_type',
            'enquiry_source', 'enquiry_status',
            'message', 'preferred_delivery_date', 'budget_range',
            'delivery_address', 'delivery_city', 'delivery_state', 'delivery_pincode',
            'assigned_to_admin', 'assigned_to_admin_username', 'assigned_at',
            'converted_to_quotation_id', 'converted_to_order_id', 'converted_at',
            'admin_notes',
            'items', 'status_history',
            'created_at', 'updated_at',
        ]

    def get_user_id(self, obj):
        return obj.user_id if obj.user_id else None

    def get_assigned_to_admin_username(self, obj):
        if obj.assigned_to_admin:
            return obj.assigned_to_admin.username
        return None


class EnquiryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for list endpoints (no nested items)."""
    item_count = serializers.SerializerMethodField()
    assigned_to_admin_username = serializers.SerializerMethodField()

    class Meta:
        model = Enquiry
        fields = [
            'id', 'public_id',
            'customer_name', 'customer_email', 'customer_phone',
            'company_name', 'business_type',
            'enquiry_source', 'enquiry_status',
            'message', 'budget_range',
            'assigned_to_admin', 'assigned_to_admin_username',
            'item_count',
            'created_at', 'updated_at',
        ]

    def get_item_count(self, obj):
        return obj.items.count()

    def get_assigned_to_admin_username(self, obj):
        if obj.assigned_to_admin:
            return obj.assigned_to_admin.username
        return None


# ============================================================================
# WRITE serializers (used in create / update)
# ============================================================================

class EnquiryItemWriteSerializer(serializers.Serializer):
    """Validates a single line-item inside an enquiry."""
    product_id = serializers.IntegerField()
    variant_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    quantity = serializers.IntegerField(min_value=1)
    notes = serializers.CharField(required=False, allow_blank=True, default='')


class EnquiryCreateSerializer(serializers.Serializer):
    """
    Validates the payload for creating a new enquiry.
    Items are passed as nested list.
    """
    customer_name = serializers.CharField(max_length=255)
    customer_email = serializers.EmailField(required=False, allow_blank=True, default='')
    customer_phone = serializers.CharField(max_length=20)
    company_name = serializers.CharField(required=False, allow_blank=True, default='')
    business_type = serializers.ChoiceField(
        choices=BusinessType.choices, required=False, allow_blank=True, default='',
    )
    enquiry_source = serializers.ChoiceField(
        choices=EnquirySource.choices, required=False, default=EnquirySource.WEBSITE,
    )
    message = serializers.CharField(required=False, allow_blank=True, default='')
    preferred_delivery_date = serializers.DateField(required=False, allow_null=True, default=None)
    budget_range = serializers.CharField(required=False, allow_blank=True, default='')

    delivery_address = serializers.CharField(required=False, allow_blank=True, default='')
    delivery_city = serializers.CharField(required=False, allow_blank=True, default='')
    delivery_state = serializers.CharField(required=False, allow_blank=True, default='')
    delivery_pincode = serializers.CharField(required=False, allow_blank=True, default='')

    items = EnquiryItemWriteSerializer(many=True, required=False, default=list)


class EnquiryUpdateSerializer(serializers.Serializer):
    """Validates partial updates on an enquiry (admin actions)."""
    enquiry_status = serializers.ChoiceField(
        choices=EnquiryStatus.choices, required=False,
    )
    assigned_to_admin = serializers.IntegerField(required=False, allow_null=True)
    admin_notes = serializers.CharField(required=False, allow_blank=True)
    message = serializers.CharField(required=False, allow_blank=True)
    status_note = serializers.CharField(
        required=False, allow_blank=True, default='',
        help_text='Optional note recorded in status-change history.',
    )


class ContactUsCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating contact form submissions."""

    class Meta:
        model = ContactUs
        fields = ['name', 'phone', 'organisation', 'category', 'email', 'message']


class ContactUsReadSerializer(serializers.ModelSerializer):
    """Serializer used in API responses/admin listing."""

    class Meta:
        model = ContactUs
        fields = [
            'id',
            'name',
            'phone',
            'organisation',
            'category',
            'email',
            'message',
            'created_at',
        ]
