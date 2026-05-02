"""
Enquiry Views
==============
CRUD API endpoints for Enquiry management.

Endpoints:
    GET    /api/enquiries/              — list all enquiries (admin) / own (user)
    POST   /api/enquiries/create/       — create a new enquiry
    GET    /api/enquiries/<id>/         — retrieve single enquiry detail
    PUT    /api/enquiries/<id>/update/  — update enquiry (status, assign, notes)
    DELETE /api/enquiries/<id>/delete/  — soft-delete / hard-delete enquiry
"""

import logging

from django.contrib.auth.models import User as AuthUser
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from categories.models import Product, ProductVariant
from identity.models import User

from .models import Enquiry, EnquiryItem, EnquiryStatusHistory, ContactUs
from .serializers import (
    ContactUsCreateSerializer,
    ContactUsReadSerializer,
    EnquiryCreateSerializer,
    EnquiryItemWriteSerializer,
    EnquiryListSerializer,
    EnquiryReadSerializer,
    EnquiryUpdateSerializer,
)

logger = logging.getLogger(__name__)


def _api(data=None, code=200, message="Success", http_status=None):
    return Response(
        {"code": code, "message": message, "data": data or {}},
        status=http_status or code,
    )


def _deny_if_no_perm(request, perm_codename: str, error_message: str = "Permission denied."):
    if not request.user.has_perm(perm_codename):
        return _api({"error": error_message}, code=403, message="Forbidden", http_status=403)
    return None


# ============================================================================
# LIST — GET /api/enquiries/
# ============================================================================

class EnquiryListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        deny = _deny_if_no_perm(request, "enquiry.view_enquiry", "You do not have permission to view enquiries.")
        if deny:
            return deny

        qs = Enquiry.objects.select_related('assigned_to_admin').order_by('-created_at')

        # Optional filters via query params
        st = request.query_params.get('status')
        if st:
            qs = qs.filter(enquiry_status=st)

        source = request.query_params.get('source')
        if source:
            qs = qs.filter(enquiry_source=source)

        search = request.query_params.get('search', '').strip()
        if search:
            from django.db.models import Q
            qs = qs.filter(
                Q(customer_name__icontains=search)
                | Q(customer_email__icontains=search)
                | Q(customer_phone__icontains=search)
                | Q(company_name__icontains=search)
            )

        serializer = EnquiryListSerializer(qs, many=True)
        return _api({"enquiries": serializer.data})


# ============================================================================
# CREATE — POST /api/enquiries/create/
# ============================================================================

class EnquiryCreateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        ser = EnquiryCreateSerializer(data=request.data)
        if not ser.is_valid():
            return _api({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data

        # Auto-link to identity_user if phone matches
        linked_user = User.objects.filter(phone=d["customer_phone"]).first()

        enquiry = Enquiry.objects.create(
            user=linked_user,
            customer_name=d["customer_name"],
            customer_email=d.get("customer_email") or None,
            customer_phone=d["customer_phone"],
            company_name=d.get("company_name") or None,
            business_type=d.get("business_type") or None,
            enquiry_source=d.get("enquiry_source", "website"),
            message=d.get("message") or None,
            preferred_delivery_date=d.get("preferred_delivery_date"),
            budget_range=d.get("budget_range") or None,
            delivery_address=d.get("delivery_address") or None,
            delivery_city=d.get("delivery_city") or None,
            delivery_state=d.get("delivery_state") or None,
            delivery_pincode=d.get("delivery_pincode") or None,
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            referrer_url=request.META.get("HTTP_REFERER", ""),
            utm_source=request.query_params.get("utm_source", ""),
            utm_medium=request.query_params.get("utm_medium", ""),
            utm_campaign=request.query_params.get("utm_campaign", ""),
        )

        # Create line items
        items_data = d.get("items", [])
        for item in items_data:
            product = Product.objects.filter(id=item["product_id"]).first()
            if not product:
                continue
            variant = None
            if item.get("variant_id"):
                variant = ProductVariant.objects.filter(id=item["variant_id"]).first()

            EnquiryItem.objects.create(
                enquiry=enquiry,
                product=product,
                variant=variant,
                product_name=product.name,
                product_sku=product.sku,
                unit_price=product.base_price,
                quantity=item["quantity"],
                notes=item.get("notes") or None,
            )

        # Create initial status history
        EnquiryStatusHistory.objects.create(
            enquiry=enquiry,
            from_status=None,
            to_status=enquiry.enquiry_status,
            notes="Enquiry created.",
        )

        logger.info("[ENQUIRY] Created enquiry #%d for %s", enquiry.id, enquiry.customer_name)

        return _api(
            {"enquiry": EnquiryReadSerializer(enquiry).data},
            code=201,
            message="Enquiry created successfully.",
            http_status=201,
        )


# ============================================================================
# DETAIL — GET /api/enquiries/<id>/
# ============================================================================

class EnquiryDetailView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request, pk):
        deny = _deny_if_no_perm(request, "enquiry.view_enquiry", "You do not have permission to view enquiries.")
        if deny:
            return deny

        try:
            enquiry = Enquiry.objects.select_related('assigned_to_admin', 'user').prefetch_related(
                'items__product', 'items__variant', 'status_history__changed_by'
            ).get(pk=pk)
        except Enquiry.DoesNotExist:
            return _api({"error": "Enquiry not found."}, code=404, message="Not found", http_status=404)

        return _api({"enquiry": EnquiryReadSerializer(enquiry).data})


# ============================================================================
# UPDATE — PUT /api/enquiries/<id>/update/
# ============================================================================

class EnquiryUpdateView(APIView):
    permission_classes = [IsAdminUser]

    def put(self, request, pk):
        deny = _deny_if_no_perm(request, "enquiry.change_enquiry", "You do not have permission to update enquiries.")
        if deny:
            return deny

        try:
            enquiry = Enquiry.objects.get(pk=pk)
        except Enquiry.DoesNotExist:
            return _api({"error": "Enquiry not found."}, code=404, message="Not found", http_status=404)

        ser = EnquiryUpdateSerializer(data=request.data)
        if not ser.is_valid():
            return _api({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        d = ser.validated_data
        old_status = enquiry.enquiry_status

        # Status change
        if "enquiry_status" in d and d["enquiry_status"] != old_status:
            enquiry.enquiry_status = d["enquiry_status"]
            EnquiryStatusHistory.objects.create(
                enquiry=enquiry,
                from_status=old_status,
                to_status=d["enquiry_status"],
                changed_by=request.user if request.user.is_authenticated else None,
                notes=d.get("status_note", ""),
            )

        # Admin assignment
        if "assigned_to_admin" in d:
            if d["assigned_to_admin"] is None:
                enquiry.assigned_to_admin = None
                enquiry.assigned_at = None
            else:
                admin_user = AuthUser.objects.filter(pk=d["assigned_to_admin"]).first()
                if admin_user:
                    enquiry.assigned_to_admin = admin_user
                    enquiry.assigned_at = timezone.now()

        if "admin_notes" in d:
            enquiry.admin_notes = d["admin_notes"]
        if "message" in d:
            enquiry.message = d["message"]

        enquiry.save()

        logger.info("[ENQUIRY] Updated enquiry #%d", enquiry.id)
        return _api({"enquiry": EnquiryReadSerializer(enquiry).data}, message="Enquiry updated.")


# ============================================================================
# DELETE — DELETE /api/enquiries/<id>/delete/
# ============================================================================

class EnquiryDeleteView(APIView):
    permission_classes = [IsAdminUser]

    def delete(self, request, pk):
        deny = _deny_if_no_perm(request, "enquiry.delete_enquiry", "You do not have permission to delete enquiries.")
        if deny:
            return deny

        try:
            enquiry = Enquiry.objects.get(pk=pk)
        except Enquiry.DoesNotExist:
            return _api({"error": "Enquiry not found."}, code=404, message="Not found", http_status=404)

        enquiry_id = enquiry.id
        enquiry.delete()
        logger.info("[ENQUIRY] Deleted enquiry #%d", enquiry_id)
        return _api(message=f"Enquiry #{enquiry_id} deleted.")


class ContactUsCreateView(APIView):
    """Public endpoint used by website Contact Us form."""

    permission_classes = [AllowAny]

    def post(self, request):
        ser = ContactUsCreateSerializer(data=request.data)
        if not ser.is_valid():
            return _api({"errors": ser.errors}, code=400, message="Validation failed", http_status=400)

        contact = ser.save(
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return _api(
            {"contact": ContactUsReadSerializer(contact).data},
            code=201,
            message="Contact request submitted successfully.",
            http_status=201,
        )


class ContactUsListView(APIView):
    """Admin-only list endpoint for contact form submissions."""

    permission_classes = [IsAdminUser]

    def get(self, request):
        if not (
            request.user.has_perm("enquiry.view_contactus")
            or request.user.has_perm("enquiry.view_enquiry")
        ):
            return _api(
                {"error": "You do not have permission to view contact submissions."},
                code=403,
                message="Forbidden",
                http_status=403,
            )

        qs = ContactUs.objects.all()
        return _api({"contacts": ContactUsReadSerializer(qs, many=True).data})


# ============================================================================
# HELPERS
# ============================================================================

def _client_ip(request) -> str:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")

