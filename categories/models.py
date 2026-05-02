import uuid

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.conf import settings


class ProductStatus(models.TextChoices):
    DRAFT = 'draft', 'Draft'
    ACTIVE = 'active', 'Active'
    INACTIVE = 'inactive', 'Inactive'
    OUT_OF_STOCK = 'out_of_stock', 'Out of Stock'


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
        indexes = [
            models.Index(fields=['slug'], name='category_slug_idx'),
            models.Index(fields=['parent'], name='category_parent_idx'),
            models.Index(fields=['level'], name='category_level_idx'),
            models.Index(fields=['is_active'], name='category_is_active_idx'),
            models.Index(fields=['is_featured'], name='category_is_featured_idx'),
            models.Index(fields=['display_order'], name='category_display_order_idx'),
            models.Index(fields=['public_id'], name='category_public_id_idx'),
        ]

    def __str__(self):
        return self.name


class SubCategory(models.Model):
    """
    Sub-level product category, linked to a parent Category.
    Mirrors the structure of Category with an explicit category FK.
    """
    public_id = models.UUIDField(unique=True, default=uuid.uuid4, editable=False)

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(null=True, blank=True)

    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='subcategories'
    )
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
        db_table = 'catalogue_subcategory'
        verbose_name = 'SubCategory'
        verbose_name_plural = 'SubCategories'
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['slug'], name='subcategory_slug_idx'),
            models.Index(fields=['category'], name='subcategory_category_idx'),
            models.Index(fields=['parent'], name='subcategory_parent_idx'),
            models.Index(fields=['level'], name='subcategory_level_idx'),
            models.Index(fields=['is_active'], name='subcategory_is_active_idx'),
            models.Index(fields=['is_featured'], name='subcategory_is_featured_idx'),
            models.Index(fields=['display_order'], name='subcategory_display_order_idx'),
            models.Index(fields=['public_id'], name='subcategory_public_id_idx'),
        ]

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

    unit = models.CharField(max_length=20, null=True, blank=True)  # kg, g, l, ml, pcs, m, cm, box, etc.
    
    # Use ArrayField for PostgreSQL, TextField for SQLite
    if 'postgresql' in settings.DATABASES['default']['ENGINE']:
        tags = ArrayField(models.CharField(max_length=100), null=True, blank=True)
        search_keywords = ArrayField(models.TextField(), null=True, blank=True)
        search_vector = SearchVectorField(null=True, blank=True)
    else:
        # SQLite fallback - store as JSON text
        tags = models.TextField(null=True, blank=True, help_text="JSON array of tags")
        search_keywords = models.TextField(null=True, blank=True, help_text="JSON array of search keywords")
        search_vector = models.TextField(null=True, blank=True, help_text="Search vector placeholder")
    
    show_in_store = models.BooleanField(default=True)   # show in online store
    track_inventory = models.BooleanField(default=True)  # track inventory checkbox
    return_policy = models.TextField(null=True, blank=True)  # cancellation and return policy
    specifications = models.JSONField(null=True, blank=True)  # [{key, value}, ...]
    video_url = models.TextField(null=True, blank=True)
    pdf_url = models.TextField(null=True, blank=True)

    # Full-text search (PostgreSQL tsvector — updated via signal/trigger)
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
        indexes = [
            models.Index(fields=['slug'], name='product_slug_idx'),
            models.Index(fields=['sku'], name='product_sku_idx'),
            models.Index(fields=['category'], name='product_category_idx'),
            models.Index(fields=['subcategory'], name='product_subcategory_idx'),
            models.Index(fields=['product_status'], name='product_status_idx'),
            models.Index(fields=['is_featured'], name='product_is_featured_idx'),
            models.Index(fields=['is_new_arrival'], name='product_is_new_arrival_idx'),
            models.Index(fields=['is_trending'], name='product_is_trending_idx'),
            models.Index(fields=['brand'], name='product_brand_idx'),
            models.Index(fields=['popularity_score'], name='product_popularity_score_idx'),
            models.Index(fields=['search_rank'], name='product_search_rank_idx'),
            models.Index(fields=['published_at'], name='product_published_at_idx'),
            models.Index(fields=['public_id'], name='product_public_id_idx'),
        ]

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
        indexes = [
            models.Index(fields=['product'], name='product_image_product_idx'),
            models.Index(fields=['is_primary'], name='product_image_is_primary_idx'),
            models.Index(fields=['display_order'], name='prod_img_display_order_idx'),
            models.Index(fields=['public_id'], name='product_image_public_id_idx'),
        ]

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
        indexes = [
            models.Index(fields=['product'], name='product_variant_product_idx'),
            models.Index(fields=['sku'], name='product_variant_sku_idx'),
            models.Index(fields=['is_active'], name='product_variant_is_active_idx'),
            models.Index(fields=['public_id'], name='product_variant_public_id_idx'),
        ]

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
        indexes = [
            models.Index(fields=['slug'], name='attribute_slug_idx'),
            models.Index(fields=['is_filterable'], name='attribute_is_filterable_idx'),
            models.Index(fields=['is_searchable'], name='attribute_is_searchable_idx'),
            models.Index(fields=['display_order'], name='attribute_display_order_idx'),
            models.Index(fields=['public_id'], name='attribute_public_id_idx'),
        ]

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
        indexes = [
            models.Index(fields=['attribute'], name='attr_value_attribute_idx'),
            models.Index(fields=['slug'], name='attr_value_slug_idx'),
            models.Index(fields=['display_order'], name='attr_value_display_order_idx'),
            models.Index(fields=['public_id'], name='attr_value_public_id_idx'),
        ]

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
        indexes = [
            models.Index(fields=['product'], name='product_attr_product_idx'),
            models.Index(fields=['attribute'], name='product_attr_attribute_idx'),
            models.Index(fields=['attribute_value'], name='prod_attr_attr_value_idx'),
        ]

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
        indexes = [
            models.Index(fields=['keyword'], name='srch_sugg_keyword_idx'),
            models.Index(fields=['suggestion_type'], name='srch_sugg_type_idx'),
            models.Index(fields=['entity_id'], name='srch_sugg_entity_id_idx'),
            models.Index(fields=['is_active'], name='srch_sugg_is_active_idx'),
            models.Index(fields=['relevance_score'], name='srch_sugg_relevance_idx'),
            models.Index(fields=['search_count'], name='srch_sugg_search_count_idx'),
            models.Index(fields=['public_id'], name='srch_sugg_public_id_idx'),
        ]

    def __str__(self):
        return self.keyword