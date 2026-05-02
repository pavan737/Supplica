"""
Category & SubCategory Views
==============================
Admin CRUD + public listing APIs for categories and subcategories.

Admin endpoints require JWT auth + staff/superuser role.
Public list endpoints return only active items with pagination.
"""

from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Category, SubCategory, Product, ProductImage
from .serializers import (
    CategorySerializer,
    CategoryListSerializer,
    SubCategorySerializer,
    SubCategoryListSerializer,
    ProductSerializer,
    ProductListSerializer,
    ProductImageSerializer,
)
from utils.dictionary import (
    is_admin,
    unique_slug,
    validate_image,
    upload_category_image,
    upload_subcategory_image,
    upload_product_image,
    upload_product_video,
    upload_product_pdf,
)


# ─────────────────────────────────────────────────────────────
# Pagination helper
# ─────────────────────────────────────────────────────────────

def _paginate(queryset, request):
    """
    Apply page / page_size pagination to a queryset.
    Returns (page_qs, meta_dict).
    """
    total_count = queryset.count()

    try:
        page = max(int(request.query_params.get("page", 1)), 1)
    except (ValueError, TypeError):
        page = 1

    try:
        page_size = min(max(int(request.query_params.get("page_size", 10)), 1), 100)
    except (ValueError, TypeError):
        page_size = 10

    start = (page - 1) * page_size
    end = start + page_size
    page_qs = queryset[start:end]

    items_on_page = len(page_qs)
    items_remaining = max(total_count - (start + items_on_page), 0)

    return page_qs, {
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "items_remaining": items_remaining,
    }


def _parse_bool_param(raw_value):
    """
    Parse a truthy/falsey query param value.
    Returns True / False / None (invalid or not provided).
    """
    if raw_value is None:
        return None

    value = str(raw_value).strip().lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    return None


def _parse_int_param(raw_value):
    """Parse integer query param; return None for invalid values."""
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _parse_decimal_param(raw_value):
    """Parse decimal query param; return None for invalid values."""
    if raw_value in (None, ""):
        return None

    try:
        return Decimal(str(raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _apply_sorting(queryset, request, sort_map, default_sort):
    """
    Apply safe sorting based on 'sort_by'.
    Invalid values fall back to default ordering.
    """
    sort_by = (request.query_params.get("sort_by") or "").strip().lower()
    order_fields = sort_map.get(sort_by, default_sort)
    return queryset.order_by(*order_fields)


def _apply_category_filters(queryset, request):
    """Apply category filters; invalid values are ignored."""
    parent_id = _parse_int_param(request.query_params.get("parent"))
    if parent_id is not None:
        queryset = queryset.filter(parent_id=parent_id)

    is_active = _parse_bool_param(request.query_params.get("is_active"))
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    is_featured = _parse_bool_param(request.query_params.get("is_featured"))
    if is_featured is not None:
        queryset = queryset.filter(is_featured=is_featured)

    search = (request.query_params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(name__icontains=search)

    return queryset


def _apply_subcategory_filters(queryset, request):
    """Apply subcategory filters; invalid values are ignored."""
    category_id = _parse_int_param(request.query_params.get("category"))
    if category_id is not None:
        queryset = queryset.filter(category_id=category_id)

    parent_id = _parse_int_param(request.query_params.get("parent"))
    if parent_id is not None:
        queryset = queryset.filter(parent_id=parent_id)

    is_active = _parse_bool_param(request.query_params.get("is_active"))
    if is_active is not None:
        queryset = queryset.filter(is_active=is_active)

    is_featured = _parse_bool_param(request.query_params.get("is_featured"))
    if is_featured is not None:
        queryset = queryset.filter(is_featured=is_featured)

    search = (request.query_params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(name__icontains=search)

    return queryset


def _apply_product_filters(queryset, request):
    """Apply product filters; invalid values are ignored."""
    category_id = _parse_int_param(request.query_params.get("category"))
    if category_id is not None:
        queryset = queryset.filter(category_id=category_id)

    subcategory_id = _parse_int_param(request.query_params.get("subcategory"))
    if subcategory_id is not None:
        queryset = queryset.filter(subcategory_id=subcategory_id)

    brand = (request.query_params.get("brand") or "").strip()
    if brand:
        queryset = queryset.filter(brand__iexact=brand)

    # Keep backward compatibility for both 'status' and 'product_status'.
    requested_status = (
        request.query_params.get("product_status")
        or request.query_params.get("status")
        or ""
    ).strip()
    valid_statuses = {choice[0] for choice in Product._meta.get_field("product_status").choices}
    if requested_status in valid_statuses:
        queryset = queryset.filter(product_status=requested_status)

    featured = _parse_bool_param(request.query_params.get("featured"))
    if featured is not None:
        queryset = queryset.filter(is_featured=featured)

    is_new = _parse_bool_param(request.query_params.get("new"))
    if is_new is not None:
        queryset = queryset.filter(is_new_arrival=is_new)

    trending = _parse_bool_param(request.query_params.get("trending"))
    if trending is not None:
        queryset = queryset.filter(is_trending=trending)

    min_price = _parse_decimal_param(request.query_params.get("min_price"))
    if min_price is not None:
        queryset = queryset.filter(base_price__gte=min_price)

    max_price = _parse_decimal_param(request.query_params.get("max_price"))
    if max_price is not None:
        queryset = queryset.filter(base_price__lte=max_price)

    in_stock = _parse_bool_param(request.query_params.get("in_stock"))
    if in_stock is True:
        queryset = queryset.filter(stock_quantity__gt=0)
    elif in_stock is False:
        queryset = queryset.filter(stock_quantity__lte=0)

    low_stock = _parse_bool_param(request.query_params.get("low_stock"))
    if low_stock is True:
        queryset = queryset.filter(stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold"))
    elif low_stock is False:
        queryset = queryset.filter(stock_quantity__gt=F("low_stock_threshold"))

    search = (request.query_params.get("search") or "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(sku__icontains=search)
            | Q(brand__icontains=search)
        )

    return queryset


CATEGORY_SORT_MAP = {
    "display_asc": ("display_order", "name", "id"),
    "display_desc": ("-display_order", "name", "id"),
    "name_asc": ("name", "id"),
    "name_desc": ("-name", "id"),
    "newest": ("-id",),
    "oldest": ("id",),
}
CATEGORY_DEFAULT_SORT = ("display_order", "name", "id")

SUBCATEGORY_SORT_MAP = {
    "display_asc": ("display_order", "name", "id"),
    "display_desc": ("-display_order", "name", "id"),
    "name_asc": ("name", "id"),
    "name_desc": ("-name", "id"),
    "newest": ("-id",),
    "oldest": ("id",),
}
SUBCATEGORY_DEFAULT_SORT = ("display_order", "name", "id")

PRODUCT_SORT_MAP = {
    "price_asc": ("base_price", "id"),
    "price_desc": ("-base_price", "id"),
    "newest": ("-created_at", "-id"),
    "oldest": ("created_at", "id"),
    "name_asc": ("name", "id"),
    "name_desc": ("-name", "id"),
}
PRODUCT_DEFAULT_SORT = ("-created_at", "-id")


# ─────────────────────────────────────────────────────────────
# IMAGE helper (shared by category & subcategory create/update)
# ─────────────────────────────────────────────────────────────

def _handle_image_upload(request):
    """
    Validate the 'image' field from request.FILES.
    Returns (image_file | None, error_response | None).
    """
    image_file = request.FILES.get("image")
    if image_file is None:
        return None, None

    is_valid, error_msg = validate_image(image_file)
    if not is_valid:
        return None, Response(
            {"error": error_msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return image_file, None


# ═════════════════════════════════════════════════════════════
#  CATEGORY — ADMIN CRUD
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_list_categories(request):
    """
    Admin: list ALL categories (including inactive).

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/admin/list/

    PARAMS (optional)
    page        : 1
    page_size   : 10

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_category", "You do not have permission to view categories.")
    if deny:
        return deny

    qs = Category.objects.filter(deleted_at__isnull=True).annotate(
        subcategory_count_annotated=Count(
            "subcategories",
            filter=Q(subcategories__deleted_at__isnull=True),
            distinct=True,
        ),
        product_count_annotated=Count(
            "products",
            filter=Q(products__deleted_at__isnull=True),
            distinct=True,
        ),
    )
    page_qs, meta = _paginate(qs, request)
    serializer = CategorySerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"categories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_add_category(request):
    """
    Admin: create a new category.

    METHOD  : POST
    URL     : http://localhost:8000/api/categories/add/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data)
    name             : Electronics
    description      : Electronic gadgets
    parent           : 1
    display_order    : 1
    is_featured      : true
    is_active        : true
    meta_title       : Electronics SEO title
    meta_description : SEO description
    meta_keywords    : electronics,gadgets
    image            : <file.webp or .png>  (max 3MB)
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.add_category", "You do not have permission to add categories.")
    if deny:
        return deny

    # Validate image (if provided)
    image_file, err_resp = _handle_image_upload(request)
    if err_resp:
        return err_resp

    serializer = CategorySerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    slug = unique_slug(serializer.validated_data['name'], Category)
    category = serializer.save(slug=slug)

    # Upload image after save (need the id for folder naming)
    if image_file:
        relative_url = upload_category_image(image_file, category.id, category.name)
        image_url = f"{settings.MEDIA_URL}{relative_url}"
        category.image_url = image_url
        category.save(update_fields=['image_url'])

    return Response({
        "message": f"Category '{category.name}' created successfully.",
        "data": {"category": CategorySerializer(category).data},
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_view_category(request, pk):
    """
    Admin: retrieve a single category.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/view/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_category", "You do not have permission to view categories.")
    if deny:
        return deny

    category = get_object_or_404(Category, pk=pk, deleted_at__isnull=True)
    serializer = CategorySerializer(category)

    return Response({
        "message": "success",
        "data": {"category": serializer.data},
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_update_category(request, pk):
    """
    Admin: update a category. Send only the fields you want to change.

    METHOD  : PUT (full update) | PATCH (partial update)
    URL     : http://localhost:8000/api/categories/update/1/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data)
    name             : Electronics Updated
    description      : Updated description
    display_order    : 2
    is_featured      : false
    is_active        : true
    meta_title       : Updated SEO title
    meta_description : Updated SEO desc
    meta_keywords    : electronics,updated
    image            : <file.webp or .png>  (max 3MB)
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.change_category", "You do not have permission to update categories.")
    if deny:
        return deny

    category = get_object_or_404(Category, pk=pk, deleted_at__isnull=True)

    # Validate image (if provided)
    image_file, err_resp = _handle_image_upload(request)
    if err_resp:
        return err_resp

    partial = (request.method == 'PATCH')
    serializer = CategorySerializer(category, data=request.data, partial=partial)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_name = serializer.validated_data.get('name', category.name)
    slug = unique_slug(new_name, Category, instance_pk=category.pk)
    category = serializer.save(slug=slug)

    # Upload new image if provided
    if image_file:
        relative_url = upload_category_image(image_file, category.id, category.name)
        image_url = f"{settings.MEDIA_URL}{relative_url}"
        category.image_url = image_url
        category.save(update_fields=['image_url'])

    return Response({
        "message": f"Category '{category.name}' updated successfully.",
        "data": {"category": CategorySerializer(category).data},
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_delete_category(request, pk):
    """
    Admin: soft-delete a category. Also deactivates all its subcategories.

    METHOD  : DELETE
    URL     : http://localhost:8000/api/categories/delete/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.delete_category", "You do not have permission to delete categories.")
    if deny:
        return deny

    category = get_object_or_404(Category, pk=pk, deleted_at__isnull=True)
    category_name = category.name

    from django.utils import timezone
    category.deleted_at = timezone.now()
    category.is_active = False
    category.save(update_fields=['deleted_at', 'is_active'])

    # Also deactivate child subcategories
    SubCategory.objects.filter(category=category, deleted_at__isnull=True).update(
        is_active=False, deleted_at=timezone.now()
    )

    return Response({
        "message": f"Category '{category_name}' deleted successfully.",
    }, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  CATEGORY — PUBLIC LIST (only active)
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_list_categories(request):
    """
    Public: list active categories with pagination. No auth required.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/list/

    PARAMS (optional)
    page      : 1
    page_size : 10
    """
    qs = Category.objects.filter(is_active=True, deleted_at__isnull=True)
    page_qs, meta = _paginate(qs, request)
    serializer = CategoryListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"categories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_filter_sort_categories(request):
    """
    Public: filter/sort active categories with pagination.
    Invalid filters/sort values are ignored and defaults are applied.
    """
    qs = Category.objects.filter(is_active=True, deleted_at__isnull=True)
    qs = _apply_category_filters(qs, request)
    qs = _apply_sorting(qs, request, CATEGORY_SORT_MAP, CATEGORY_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = CategoryListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"categories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_filter_sort_categories(request):
    """
    Admin: filter/sort all non-deleted categories with pagination.
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_category", "You do not have permission to view categories.")
    if deny:
        return deny

    qs = Category.objects.filter(deleted_at__isnull=True).annotate(
        subcategory_count_annotated=Count(
            "subcategories",
            filter=Q(subcategories__deleted_at__isnull=True),
            distinct=True,
        ),
        product_count_annotated=Count(
            "products",
            filter=Q(products__deleted_at__isnull=True),
            distinct=True,
        ),
    )
    qs = _apply_category_filters(qs, request)
    qs = _apply_sorting(qs, request, CATEGORY_SORT_MAP, CATEGORY_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = CategorySerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"categories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  SUBCATEGORY — ADMIN CRUD
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_list_subcategories(request):
    """
    Admin: list ALL subcategories (including inactive).

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/subcategories/admin/list/

    PARAMS (optional)
    page        : 1
    page_size   : 10
    category    : 1

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_subcategory", "You do not have permission to view subcategories.")
    if deny:
        return deny

    qs = SubCategory.objects.filter(deleted_at__isnull=True).select_related('category')

    category_id = request.query_params.get("category")
    if category_id:
        qs = qs.filter(category_id=category_id)

    page_qs, meta = _paginate(qs, request)
    serializer = SubCategorySerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"subcategories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_add_subcategory(request):
    """
    Admin: create a new subcategory.

    METHOD  : POST
    URL     : http://localhost:8000/api/categories/subcategories/add/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data)
    name             : Smartphones
    category         : 1
    description      : All smartphones
    parent           : 2
    display_order    : 1
    is_featured      : true
    is_active        : true
    meta_title       : Smartphones SEO title
    meta_description : SEO description
    meta_keywords    : smartphones,mobile
    image            : <file.webp or .png>  (max 3MB)
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.add_subcategory", "You do not have permission to add subcategories.")
    if deny:
        return deny

    # Validate parent category exists and is active
    category_id = request.data.get("category")
    if not category_id:
        return Response({"error": "category field is required."}, status=status.HTTP_400_BAD_REQUEST)

    parent_category = Category.objects.filter(
        pk=category_id, is_active=True, deleted_at__isnull=True
    ).first()
    if not parent_category:
        return Response(
            {"error": "Invalid or inactive category ID."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate image (if provided)
    image_file, err_resp = _handle_image_upload(request)
    if err_resp:
        return err_resp

    serializer = SubCategorySerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    slug = unique_slug(serializer.validated_data['name'], SubCategory)
    subcategory = serializer.save(slug=slug)

    # Upload image after save
    if image_file:
        relative_url = upload_subcategory_image(
            image_file,
            subcategory.id, subcategory.name,
            parent_category.id, parent_category.name,
        )
        image_url = f"{settings.MEDIA_URL}{relative_url}"
        subcategory.image_url = image_url
        subcategory.save(update_fields=['image_url'])

    return Response({
        "message": f"SubCategory '{subcategory.name}' created successfully.",
        "data": {"subcategory": SubCategorySerializer(subcategory).data},
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_view_subcategory(request, pk):
    """
    Admin: retrieve a single subcategory.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/subcategories/view/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_subcategory", "You do not have permission to view subcategories.")
    if deny:
        return deny

    subcategory = get_object_or_404(
        SubCategory.objects.select_related('category'), pk=pk, deleted_at__isnull=True
    )
    serializer = SubCategorySerializer(subcategory)

    return Response({
        "message": "success",
        "data": {"subcategory": serializer.data},
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_update_subcategory(request, pk):
    """
    Admin: update a subcategory. Send only the fields you want to change.

    METHOD  : PUT (full update) | PATCH (partial update)
    URL     : http://localhost:8000/api/categories/subcategories/update/1/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data)
    name             : Smartphones Updated
    category         : 2
    description      : Updated description
    display_order    : 3
    is_featured      : false
    is_active        : true
    meta_title       : Updated SEO title
    meta_keywords    : smartphones,updated
    image            : <file.webp or .png>  (max 3MB)
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.change_subcategory", "You do not have permission to update subcategories.")
    if deny:
        return deny

    subcategory = get_object_or_404(
        SubCategory.objects.select_related('category'), pk=pk, deleted_at__isnull=True
    )

    # Validate image (if provided)
    image_file, err_resp = _handle_image_upload(request)
    if err_resp:
        return err_resp

    # If category is being changed, validate the new one
    new_category_id = request.data.get("category")
    if new_category_id:
        parent_category = Category.objects.filter(
            pk=new_category_id, is_active=True, deleted_at__isnull=True
        ).first()
        if not parent_category:
            return Response(
                {"error": "Invalid or inactive category ID."},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        parent_category = subcategory.category

    partial = (request.method == 'PATCH')
    serializer = SubCategorySerializer(subcategory, data=request.data, partial=partial)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_name = serializer.validated_data.get('name', subcategory.name)
    slug = unique_slug(new_name, SubCategory, instance_pk=subcategory.pk)
    subcategory = serializer.save(slug=slug)

    # Upload new image if provided
    if image_file and parent_category:
        relative_url = upload_subcategory_image(
            image_file,
            subcategory.id, subcategory.name,
            parent_category.id, parent_category.name,
        )
        image_url = f"{settings.MEDIA_URL}{relative_url}"
        subcategory.image_url = image_url
        subcategory.save(update_fields=['image_url'])

    return Response({
        "message": f"SubCategory '{subcategory.name}' updated successfully.",
        "data": {"subcategory": SubCategorySerializer(subcategory).data},
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_delete_subcategory(request, pk):
    """
    Admin: soft-delete a subcategory.

    METHOD  : DELETE
    URL     : http://localhost:8000/api/categories/subcategories/delete/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.delete_subcategory", "You do not have permission to delete subcategories.")
    if deny:
        return deny

    subcategory = get_object_or_404(SubCategory, pk=pk, deleted_at__isnull=True)
    subcategory_name = subcategory.name

    from django.utils import timezone
    subcategory.deleted_at = timezone.now()
    subcategory.is_active = False
    subcategory.save(update_fields=['deleted_at', 'is_active'])

    return Response({
        "message": f"SubCategory '{subcategory_name}' deleted successfully.",
    }, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  SUBCATEGORY — PUBLIC LIST (only active under active categories)
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_list_subcategories(request):
    """
    Public: list active subcategories. No auth required.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/subcategories/list/

    PARAMS (optional)
    page      : 1
    page_size : 10
    category  : 1
    """
    qs = SubCategory.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        category__is_active=True,
        category__deleted_at__isnull=True,
    ).select_related('category')

    category_id = request.query_params.get("category")
    if category_id:
        qs = qs.filter(category_id=category_id)

    page_qs, meta = _paginate(qs, request)
    serializer = SubCategoryListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"subcategories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_filter_sort_subcategories(request):
    """
    Public: filter/sort active subcategories with pagination.
    Invalid filters/sort values are ignored and defaults are applied.
    """
    qs = SubCategory.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        category__is_active=True,
        category__deleted_at__isnull=True,
    ).select_related('category')
    qs = _apply_subcategory_filters(qs, request)
    qs = _apply_sorting(qs, request, SUBCATEGORY_SORT_MAP, SUBCATEGORY_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = SubCategoryListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"subcategories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_filter_sort_subcategories(request):
    """
    Admin: filter/sort all non-deleted subcategories with pagination.
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_subcategory", "You do not have permission to view subcategories.")
    if deny:
        return deny

    qs = SubCategory.objects.filter(deleted_at__isnull=True).select_related('category')
    qs = _apply_subcategory_filters(qs, request)
    qs = _apply_sorting(qs, request, SUBCATEGORY_SORT_MAP, SUBCATEGORY_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = SubCategorySerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"subcategories": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────
# PRODUCT IMAGE helpers
# ─────────────────────────────────────────────────────────────

def _validate_images(request):
    """
    Validate all 'images' files from request.FILES.
    Returns (list_of_image_files, error_response | None).
    """
    image_files = request.FILES.getlist("images")
    if not image_files:
        return [], None

    for img in image_files:
        is_valid, error_msg = validate_image(img)
        if not is_valid:
            return [], Response(
                {"error": f"Image '{img.name}': {error_msg}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    return image_files, None


def _save_product_images(image_files, product, category):
    """
    Upload image files and create ProductImage records.
    The first image is marked as primary if no primary image exists.
    """
    has_primary = product.images.filter(is_primary=True).exists()
    next_order = product.images.count()

    for i, img_file in enumerate(image_files):
        next_order += 1
        relative_url = upload_product_image(
            img_file,
            product.id, product.name,
            category.id, category.name,
            image_index=next_order,
        )
        image_url = f"{settings.MEDIA_URL}{relative_url}"

        ProductImage.objects.create(
            product=product,
            image_url=image_url,
            display_order=next_order,
            is_primary=(not has_primary and i == 0),
            alt_text=product.name,
        )
        if not has_primary and i == 0:
            has_primary = True


def _deny_if_no_perm(request, perm_codename: str, error_message: str = "Permission denied."):
    if not request.user.has_perm(perm_codename):
        return Response({"error": error_message}, status=status.HTTP_403_FORBIDDEN)
    return None


# ═════════════════════════════════════════════════════════════
#  PRODUCT — ADMIN CRUD
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_list_products(request):
    """
    Admin: list ALL products (including inactive/draft).

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/products/admin/list/

    PARAMS (optional)
    page        : 1
    page_size   : 10
    category    : 1
    status      : active

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_product", "You do not have permission to view products.")
    if deny:
        return deny

    qs = Product.objects.filter(deleted_at__isnull=True).select_related('category').prefetch_related('images')

    # Optional filters
    category_id = request.query_params.get("category")
    if category_id:
        qs = qs.filter(category_id=category_id)

    product_status = request.query_params.get("status")
    if product_status:
        qs = qs.filter(product_status=product_status)

    page_qs, meta = _paginate(qs, request)
    serializer = ProductSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"products": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_add_product(request):
    """
    Admin: create a new product with optional image uploads.

    METHOD  : POST
    URL     : http://localhost:8000/api/categories/products/add/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data)
    name               : Blue Notebook A4
    sku                : NB-BLU-A4-001
    short_description  : Premium A4 notebook
    long_description   : Detailed description ...
    category           : 1
    subcategory        : 3    (optional)
    base_price         : 150.00
    mrp                : 200.00
    cost_price         : 80.00
    stock_quantity     : 500
    min_order_quantity : 1
    max_order_quantity : 100
    low_stock_threshold: 10
    brand              : Supplica
    manufacturer       : ABC Paper Mills
    model_number       : NB-A4
    hsn_code           : 4820
    weight_grams       : 300
    dimensions_cm      : 21x29.7x1
    meta_title         : SEO title
    meta_description   : SEO description
    meta_keywords      : notebook,a4,blue
    search_keywords    : ["notebook","a4","blue"]   (JSON array)
    product_status     : active
    is_featured        : false
    is_new_arrival     : true
    is_trending        : false
    images             : <file1.webp>  (multiple files)
    images             : <file2.png>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.add_product", "You do not have permission to add products.")
    if deny:
        return deny

    # Validate category exists and is active
    category_id = request.data.get("category")
    if not category_id:
        return Response({"error": "category field is required."}, status=status.HTTP_400_BAD_REQUEST)

    category = Category.objects.filter(
        pk=category_id, is_active=True, deleted_at__isnull=True
    ).first()
    if not category:
        return Response({"error": "Invalid or inactive category ID."}, status=status.HTTP_400_BAD_REQUEST)

    # Validate images (if provided)
    image_files, err_resp = _validate_images(request)
    if err_resp:
        return err_resp

    serializer = ProductSerializer(data=request.data)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    slug = unique_slug(serializer.validated_data['name'], Product)
    product = serializer.save(slug=slug)

    # Upload images after save (need the product id for folder naming)
    if image_files:
        _save_product_images(image_files, product, category)

    # Upload video (if provided)
    video_file = request.FILES.get("video")
    if video_file:
        video_url = upload_product_video(video_file, product.id, product.name, category.id, category.name)
        product.video_url = f"{settings.MEDIA_URL}{video_url}"
        product.save(update_fields=["video_url"])

    # Upload PDF (if provided)
    pdf_file = request.FILES.get("pdf")
    if pdf_file:
        pdf_url = upload_product_pdf(pdf_file, product.id, product.name, category.id, category.name)
        product.pdf_url = f"{settings.MEDIA_URL}{pdf_url}"
        product.save(update_fields=["pdf_url"])

    # Re-fetch with images for response
    product.refresh_from_db()
    return Response({
        "message": f"Product '{product.name}' created successfully.",
        "data": {"product": ProductSerializer(product).data},
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_view_product(request, pk):
    """
    Admin: retrieve a single product with all images.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/products/view/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_product", "You do not have permission to view products.")
    if deny:
        return deny

    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('images'),
        pk=pk,
        deleted_at__isnull=True,
    )
    serializer = ProductSerializer(product)

    return Response({
        "message": "success",
        "data": {"product": serializer.data},
    }, status=status.HTTP_200_OK)


@api_view(['PUT', 'PATCH'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_update_product(request, pk):
    """
    Admin: update a product. Send only the fields you want to change.
    New images are appended; existing images are preserved.

    METHOD  : PUT (full update) | PATCH (partial update)
    URL     : http://localhost:8000/api/categories/products/update/1/

    HEADERS
    Authorization  : Bearer <access_token>
    Content-Type   : multipart/form-data

    BODY (form-data) — all fields optional for PATCH
    name               : Updated Notebook
    sku                : NB-BLU-A4-002
    base_price         : 175.00
    product_status     : active
    images             : <new_file.webp>  (appended)
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.change_product", "You do not have permission to update products.")
    if deny:
        return deny

    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('images'),
        pk=pk,
        deleted_at__isnull=True,
    )

    # If category is being changed, validate the new one
    new_category_id = request.data.get("category")
    if new_category_id:
        category = Category.objects.filter(
            pk=new_category_id, is_active=True, deleted_at__isnull=True
        ).first()
        if not category:
            return Response({"error": "Invalid or inactive category ID."}, status=status.HTTP_400_BAD_REQUEST)
    else:
        category = product.category

    # Validate images (if provided)
    image_files, err_resp = _validate_images(request)
    if err_resp:
        return err_resp

    partial = (request.method == 'PATCH')
    serializer = ProductSerializer(product, data=request.data, partial=partial)
    if not serializer.is_valid():
        return Response({"error": serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

    new_name = serializer.validated_data.get('name', product.name)
    slug = unique_slug(new_name, Product, instance_pk=product.pk)
    product = serializer.save(slug=slug)

    # Upload new images if provided (appended to existing)
    if image_files:
        _save_product_images(image_files, product, category)

    # Upload new video if provided
    video_file = request.FILES.get("video")
    if video_file:
        video_url = upload_product_video(video_file, product.id, product.name, category.id, category.name)
        product.video_url = f"{settings.MEDIA_URL}{video_url}"
        product.save(update_fields=["video_url"])

    # Upload new PDF if provided
    pdf_file = request.FILES.get("pdf")
    if pdf_file:
        pdf_url = upload_product_pdf(pdf_file, product.id, product.name, category.id, category.name)
        product.pdf_url = f"{settings.MEDIA_URL}{pdf_url}"
        product.save(update_fields=["pdf_url"])

    product.refresh_from_db()
    return Response({
        "message": f"Product '{product.name}' updated successfully.",
        "data": {"product": ProductSerializer(product).data},
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_delete_product(request, pk):
    """
    Admin: soft-delete a product.

    METHOD  : DELETE
    URL     : http://localhost:8000/api/categories/products/delete/1/

    HEADERS
    Authorization : Bearer <access_token>
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.delete_product", "You do not have permission to delete products.")
    if deny:
        return deny

    product = get_object_or_404(Product, pk=pk, deleted_at__isnull=True)
    product_name = product.name

    product.deleted_at = timezone.now()
    product.product_status = 'inactive'
    product.save(update_fields=['deleted_at', 'product_status'])

    return Response({
        "message": f"Product '{product_name}' deleted successfully.",
    }, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  PRODUCT — PUBLIC LIST (only active)
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_list_products(request):
    """
    Public: list active products with pagination. No auth required.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/products/list/

    PARAMS (optional)
    page      : 1
    page_size : 10
    category  : 1
    brand     : Supplica
    featured  : true
    new       : true
    trending  : true
    """
    qs = Product.objects.filter(
        product_status='active',
        deleted_at__isnull=True,
        category__is_active=True,
        category__deleted_at__isnull=True,
    ).select_related('category').prefetch_related('images')

    # Optional filters
    category_id = request.query_params.get("category")
    if category_id:
        qs = qs.filter(category_id=category_id)

    brand = request.query_params.get("brand")
    if brand:
        qs = qs.filter(brand__iexact=brand)

    if request.query_params.get("featured", "").lower() == "true":
        qs = qs.filter(is_featured=True)

    if request.query_params.get("new", "").lower() == "true":
        qs = qs.filter(is_new_arrival=True)

    if request.query_params.get("trending", "").lower() == "true":
        qs = qs.filter(is_trending=True)

    page_qs, meta = _paginate(qs, request)
    serializer = ProductListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"products": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_filter_sort_products(request):
    """
    Public: filter/sort active products with pagination.
    Invalid filters/sort values are ignored and defaults are applied.
    """
    qs = Product.objects.filter(
        product_status='active',
        deleted_at__isnull=True,
        category__is_active=True,
        category__deleted_at__isnull=True,
    ).select_related('category').prefetch_related('images')

    qs = _apply_product_filters(qs, request)
    qs = _apply_sorting(qs, request, PRODUCT_SORT_MAP, PRODUCT_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = ProductListSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"products": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@authentication_classes([JWTAuthentication])
@permission_classes([IsAuthenticated])
def api_admin_filter_sort_products(request):
    """
    Admin: filter/sort all non-deleted products with pagination.
    """
    if not is_admin(request.user):
        return Response({"error": "Admin access required."}, status=status.HTTP_403_FORBIDDEN)

    deny = _deny_if_no_perm(request, "categories.view_product", "You do not have permission to view products.")
    if deny:
        return deny

    qs = Product.objects.filter(deleted_at__isnull=True).select_related('category').prefetch_related('images')
    qs = _apply_product_filters(qs, request)
    qs = _apply_sorting(qs, request, PRODUCT_SORT_MAP, PRODUCT_DEFAULT_SORT)

    page_qs, meta = _paginate(qs, request)
    serializer = ProductSerializer(page_qs, many=True)

    return Response({
        "message": "success",
        "data": {"products": serializer.data},
        "pagination": meta,
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def api_get_product(request, pk):
    """
    Public: retrieve a single active product with full details and images.

    METHOD  : GET
    URL     : http://localhost:8000/api/categories/products/1/

    No auth required.
    """
    product = get_object_or_404(
        Product.objects.select_related('category').prefetch_related('images'),
        pk=pk,
        product_status='active',
        deleted_at__isnull=True,
    )
    serializer = ProductSerializer(product)

    return Response({
        "message": "success",
        "data": {"product": serializer.data},
    }, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  SEARCH SUGGESTIONS — GET /api/categories/search/suggestions/?q=
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_search_suggestions(request):
    """
    Unified search suggestions across categories and products.
    Returns max 10 results (categories first, then products).

    METHOD  : GET
    URL     : /api/categories/search/suggestions/?q=books
    PARAMS  : q — search term (min 2 chars)
    """
    q = request.query_params.get("q", "").strip()

    if len(q) < 2:
        return Response({"results": []}, status=status.HTTP_200_OK)

    from django.conf import settings as django_settings

    results = []

    # ── Categories (ILIKE match on name) ──────────────────────
    cats = Category.objects.filter(
        is_active=True,
        deleted_at__isnull=True,
        name__icontains=q,
    ).order_by("display_order", "name")[:6]

    for cat in cats:
        img = cat.image_url or ""
        if img and not img.startswith(("http://", "https://")):
            img = f"{django_settings.MEDIA_URL}{img.lstrip('/')}"
        results.append({
            "id": cat.id,
            "type": "category",
            "name": cat.name,
            "slug": cat.slug or "",
            "image_url": img or None,
            "url": f"/products?cat={cat.name}",
        })

    # ── Products (ILIKE match on name or category name) ───────
    remaining = 10 - len(results)
    if remaining > 0:
        from django.db.models import Q
        prods = Product.objects.filter(
            product_status="active",
            deleted_at__isnull=True,
            category__is_active=True,
            category__deleted_at__isnull=True,
        ).filter(
            Q(name__icontains=q) | Q(category__name__icontains=q)
        ).select_related("category").prefetch_related("images")[:remaining]

        for prod in prods:
            primary = prod.images.filter(is_primary=True).first() or prod.images.first()
            img = primary.image_url if primary else ""
            if img and not img.startswith(("http://", "https://")):
                img = f"{django_settings.MEDIA_URL}{img.lstrip('/')}"
            results.append({
                "id": prod.id,
                "type": "product",
                "name": prod.name,
                "slug": prod.slug or "",
                "image_url": img or None,
                "url": f"/products?q={prod.name}",
                "price": float(prod.base_price) if prod.base_price else None,
                "category_name": prod.category.name if prod.category else "",
            })

    return Response({"results": results}, status=status.HTTP_200_OK)


# ═════════════════════════════════════════════════════════════
#  POPULAR PRODUCTS — Public (ordered by enquiry count)
# ═════════════════════════════════════════════════════════════

@api_view(['GET'])
@permission_classes([AllowAny])
def api_popular_products(request):
    """
    Public: list products ordered by enquiry count (most enquired first).
    Falls back to featured/trending products if no enquiry data exists.

    METHOD  : GET
    URL     : /api/categories/products/popular/
    PARAMS  : page_size (default 8, max 20)
    """
    try:
        page_size = min(int(request.query_params.get("page_size", 8)), 20)
    except (ValueError, TypeError):
        page_size = 8

    # Import here to avoid circular imports
    from django.db.models import Count as DjCount, OuterRef, Subquery, IntegerField
    from django.db.models.functions import Coalesce

    try:
        from enquiry.models import EnquiryItem

        # Subquery: count enquiry items per product
        enquiry_count_sq = (
            EnquiryItem.objects
            .filter(product_id=OuterRef('pk'))
            .values('product_id')
            .annotate(c=DjCount('id'))
            .values('c')
        )

        qs = (
            Product.objects
            .filter(product_status='active', deleted_at__isnull=True,
                    category__is_active=True, category__deleted_at__isnull=True)
            .prefetch_related('images')
            .select_related('category')
            .annotate(
                enquiry_count=Coalesce(
                    Subquery(enquiry_count_sq, output_field=IntegerField()), 0
                )
            )
            .order_by('-enquiry_count', '-is_featured', '-is_trending', '-id')
            [:page_size]
        )
    except Exception:
        # Fallback if enquiry app not available
        qs = (
            Product.objects
            .filter(product_status='active', deleted_at__isnull=True)
            .prefetch_related('images')
            .select_related('category')
            .order_by('-is_featured', '-is_trending', '-id')
            [:page_size]
        )

    serializer = ProductListSerializer(qs, many=True)
    return Response({
        "message": "success",
        "data": {"products": serializer.data},
    }, status=status.HTTP_200_OK)
