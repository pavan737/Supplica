from django.contrib import admin
from .models import Enquiry, EnquiryItem, EnquiryStatusHistory


class EnquiryItemInline(admin.TabularInline):
    model = EnquiryItem
    extra = 0
    readonly_fields = ('public_id', 'created_at')


class EnquiryStatusHistoryInline(admin.TabularInline):
    model = EnquiryStatusHistory
    extra = 0
    readonly_fields = ('from_status', 'to_status', 'changed_by', 'created_at')


@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer_name', 'customer_phone', 'enquiry_status', 'enquiry_source', 'created_at')
    list_filter = ('enquiry_status', 'enquiry_source', 'business_type')
    search_fields = ('customer_name', 'customer_email', 'customer_phone', 'company_name')
    readonly_fields = ('public_id', 'created_at', 'updated_at')
    inlines = [EnquiryItemInline, EnquiryStatusHistoryInline]


@admin.register(EnquiryItem)
class EnquiryItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'enquiry', 'product_name', 'quantity', 'unit_price')
    readonly_fields = ('public_id', 'created_at')


@admin.register(EnquiryStatusHistory)
class EnquiryStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ('enquiry', 'from_status', 'to_status', 'changed_by', 'created_at')
    readonly_fields = ('created_at',)
