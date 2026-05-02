from rest_framework import serializers
from .models import Category, SubCategory, Product, ProductImage


# =============================================================================
# CATEGORY
# =============================================================================

class CategorySerializer(serializers.ModelSerializer):
    """
    Full serializer used in admin CRUD responses.
    slug, public_id, timestamps are read-only.
    """
    subcategory_count = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'description',
            'parent',
            'level',
            'path',
            'meta_title',
            'meta_description',
            'meta_keywords',
            'image_url',
            'icon_url',
            'display_order',
            'is_featured',
            'is_active',
            'created_at',
            'updated_at',
            'subcategory_count',
            'product_count',
        ]
        read_only_fields = [
            'id', 'public_id', 'slug', 'image_url',
            'created_at', 'updated_at',
        ]

    def get_subcategory_count(self, obj):
        annotated_count = getattr(obj, 'subcategory_count_annotated', None)
        if annotated_count is not None:
            return annotated_count
        return obj.subcategories.count()

    def get_product_count(self, obj):
        annotated_count = getattr(obj, 'product_count_annotated', None)
        if annotated_count is not None:
            return annotated_count
        return obj.products.count()


class CategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for public listing (no meta/admin fields)."""

    class Meta:
        model = Category
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'description',
            'image_url',
            'icon_url',
            'display_order',
            'is_featured',
        ]


# =============================================================================
# SUBCATEGORY
# =============================================================================

class SubCategorySerializer(serializers.ModelSerializer):
    """Full serializer for admin CRUD on subcategories."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = SubCategory
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'description',
            'category',
            'category_name',
            'parent',
            'level',
            'path',
            'meta_title',
            'meta_description',
            'meta_keywords',
            'image_url',
            'icon_url',
            'display_order',
            'is_featured',
            'is_active',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id', 'public_id', 'slug', 'image_url',
            'created_at', 'updated_at',
        ]


class SubCategoryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for public listing."""
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = SubCategory
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'description',
            'category',
            'category_name',
            'image_url',
            'icon_url',
            'display_order',
            'is_featured',
        ]


# =============================================================================
# PRODUCT IMAGE
# =============================================================================

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = [
            'id',
            'public_id',
            'image_url',
            'thumbnail_url',
            'display_order',
            'is_primary',
            'alt_text',
            'created_at',
        ]
        read_only_fields = ['id', 'public_id', 'image_url', 'created_at']


# =============================================================================
# PRODUCT — FULL (Admin CRUD)
# =============================================================================

class ProductSerializer(serializers.ModelSerializer):
    """Full serializer used in admin CRUD responses."""
    images = ProductImageSerializer(many=True, read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'sku',
            'short_description',
            'long_description',
            'category',
            'category_name',
            'subcategory',
            'base_price',
            'mrp',
            'cost_price',
            'stock_quantity',
            'min_order_quantity',
            'max_order_quantity',
            'low_stock_threshold',
            'brand',
            'manufacturer',
            'model_number',
            'hsn_code',
            'weight_grams',
            'dimensions_cm',
            'meta_title',
            'meta_description',
            'meta_keywords',
            'unit',
            'tags',
            'show_in_store',
            'track_inventory',
            'return_policy',
            'specifications',
            'video_url',
            'pdf_url',
            'search_keywords',
            'popularity_score',
            'search_rank',
            'product_status',
            'is_featured',
            'is_new_arrival',
            'is_trending',
            'published_at',
            'created_at',
            'updated_at',
            'images',
        ]
        read_only_fields = [
            'id', 'public_id', 'slug',
            'video_url', 'pdf_url',
            'popularity_score', 'search_rank',
            'created_at', 'updated_at',
        ]


# =============================================================================
# PRODUCT — LIGHTWEIGHT (Public listing)
# =============================================================================

class ProductListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for public product listing."""
    primary_image = serializers.SerializerMethodField()
    category_name = serializers.CharField(source='category.name', read_only=True)

    class Meta:
        model = Product
        fields = [
            'id',
            'public_id',
            'name',
            'slug',
            'sku',
            'short_description',
            'category',
            'category_name',
            'base_price',
            'mrp',
            'stock_quantity',
            'brand',
            'unit',
            'tags',
            'show_in_store',
            'product_status',
            'is_featured',
            'is_new_arrival',
            'is_trending',
            'primary_image',
        ]

    def get_primary_image(self, obj):
        images = list(obj.images.all())
        if not images:
            return None

        primary = next((img for img in images if img.is_primary), None)
        if not primary:
            primary = images[0]

        if primary:
            return ProductImageSerializer(primary).data
        return None


