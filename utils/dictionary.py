"""
Reusable utility functions for the Supplica backend.
Image validation, folder generation, and file upload helpers.
"""

import os
import re

from django.conf import settings
from django.utils.text import slugify


# =============================================================================
# CONSTANTS
# =============================================================================

MAX_IMAGE_SIZE_BYTES = 3 * 1024 * 1024  # 3 MB
ALLOWED_IMAGE_TYPES = {"image/webp", "image/png", "image/jpeg"}
ALLOWED_EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}

MAX_VIDEO_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/ogg", "video/quicktime"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4", ".webm", ".ogg", ".mov"}

MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024  # 20 MB


# =============================================================================
# IMAGE VALIDATION
# =============================================================================

def validate_image(image_file):
    """
    Validate an uploaded image file for size and format.
    Returns (is_valid: bool, error_message: str | None).
    """
    if image_file is None:
        return False, "No image file provided."

    # Size check
    if image_file.size > MAX_IMAGE_SIZE_BYTES:
        size_mb = round(image_file.size / (1024 * 1024), 2)
        return False, f"Image size {size_mb}MB exceeds the 3MB limit."

    # Content type check
    content_type = getattr(image_file, "content_type", "")
    if content_type not in ALLOWED_IMAGE_TYPES:
        return False, f"Invalid image format '{content_type}'. Only JPEG, PNG and WEBP are allowed."

    # Extension check
    _, ext = os.path.splitext(image_file.name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False, f"Invalid file extension '{ext}'. Only .jpg, .jpeg, .png and .webp are allowed."

    return True, None


# =============================================================================
# FOLDER / PATH GENERATION
# =============================================================================

def generate_category_folder(category_id, category_name):
    """
    Build the folder path for a category image.
    Example: media/category/category--01--electronics/
    """
    safe_name = slugify(category_name)
    folder_name = f"category--{category_id:02d}--{safe_name}"
    return os.path.join("category", folder_name)


def generate_subcategory_folder(subcategory_id, subcategory_name, category_id, category_name):
    """
    Build the folder path for a subcategory image.
    Example: media/category/category--01--electronics/subcategory--03--phones/
    """
    cat_folder = generate_category_folder(category_id, category_name)
    safe_name = slugify(subcategory_name)
    sub_folder = f"subcategory--{subcategory_id:02d}--{safe_name}"
    return os.path.join(cat_folder, sub_folder)


# =============================================================================
# IMAGE UPLOAD
# =============================================================================

def upload_category_image(image_file, category_id, category_name):
    """
    Save an image to the category folder inside MEDIA_ROOT.
    Returns the relative URL path (e.g. 'category/category--01--electronics/image.webp').
    """
    relative_folder = generate_category_folder(category_id, category_name)
    return _save_image(image_file, relative_folder)


def upload_subcategory_image(image_file, subcategory_id, subcategory_name, category_id, category_name):
    """
    Save an image to the subcategory folder inside MEDIA_ROOT.
    Returns the relative URL path.
    """
    relative_folder = generate_subcategory_folder(
        subcategory_id, subcategory_name, category_id, category_name
    )
    return _save_image(image_file, relative_folder)


def _save_image(image_file, relative_folder):
    """
    Write the uploaded file to disk and return its media-relative path.
    Overwrites any existing image in the same folder.
    """
    abs_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(abs_folder, exist_ok=True)

    _, ext = os.path.splitext(image_file.name)
    filename = f"image{ext.lower()}"
    abs_path = os.path.join(abs_folder, filename)

    with open(abs_path, "wb+") as dest:
        for chunk in image_file.chunks():
            dest.write(chunk)

    # Return forward-slash relative path for DB / URL usage
    return os.path.join(relative_folder, filename).replace("\\", "/")


# =============================================================================
# SLUG HELPERS
# =============================================================================

def unique_slug(name, model_class, instance_pk=None):
    """
    Generate a unique slug for any model that has a 'slug' field.
    Appends -2, -3, … if the base slug is already taken.
    """
    base = slugify(name)
    slug = base
    counter = 2
    qs = model_class.objects.all()
    if instance_pk:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{counter}"
        counter += 1
    return slug


# =============================================================================
# ADMIN CHECK
# =============================================================================

def is_admin(user):
    """Return True if the user is staff or superuser."""
    return user.is_staff or user.is_superuser


# =============================================================================
# PRODUCT IMAGE UPLOAD
# =============================================================================

def generate_product_image_folder(product_id, product_name, category_id, category_name):
    """
    Build the folder path for product images.
    Example: category/category--01--electronics/products/product--05--laptop/
    """
    cat_folder = generate_category_folder(category_id, category_name)
    safe_name = slugify(product_name)
    prod_folder = f"product--{product_id:02d}--{safe_name}"
    return os.path.join(cat_folder, "products", prod_folder)


def upload_product_image(image_file, product_id, product_name, category_id, category_name, image_index=1):
    """
    Save an image to the product folder inside MEDIA_ROOT.
    Returns the relative URL path (e.g. 'category/category--01--electronics/products/product--05--laptop/image_01.webp').
    """
    relative_folder = generate_product_image_folder(
        product_id, product_name, category_id, category_name
    )
    abs_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(abs_folder, exist_ok=True)

    _, ext = os.path.splitext(image_file.name)
    filename = f"image_{image_index:02d}{ext.lower()}"
    abs_path = os.path.join(abs_folder, filename)

    with open(abs_path, "wb+") as dest:
        for chunk in image_file.chunks():
            dest.write(chunk)

    return os.path.join(relative_folder, filename).replace("\\", "/")


# =============================================================================
# PRODUCT VIDEO UPLOAD
# =============================================================================

def validate_video(video_file):
    """Validate an uploaded video file for size and format."""
    if video_file is None:
        return False, "No video file provided."
    if video_file.size > MAX_VIDEO_SIZE_BYTES:
        size_mb = round(video_file.size / (1024 * 1024), 2)
        return False, f"Video size {size_mb}MB exceeds the 100MB limit."
    content_type = getattr(video_file, "content_type", "")
    if content_type not in ALLOWED_VIDEO_TYPES:
        return False, f"Invalid video format '{content_type}'. Only MP4, WebM, OGG and MOV are allowed."
    _, ext = os.path.splitext(video_file.name)
    if ext.lower() not in ALLOWED_VIDEO_EXTENSIONS:
        return False, f"Invalid file extension '{ext}'. Only .mp4, .webm, .ogg and .mov are allowed."
    return True, None


def upload_product_video(video_file, product_id, product_name, category_id, category_name):
    """Save a product video and return its media-relative path."""
    relative_folder = generate_product_image_folder(product_id, product_name, category_id, category_name)
    abs_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(abs_folder, exist_ok=True)
    _, ext = os.path.splitext(video_file.name)
    filename = f"video{ext.lower()}"
    abs_path = os.path.join(abs_folder, filename)
    with open(abs_path, "wb+") as dest:
        for chunk in video_file.chunks():
            dest.write(chunk)
    return os.path.join(relative_folder, filename).replace("\\", "/")


# =============================================================================
# PRODUCT PDF UPLOAD
# =============================================================================

def validate_pdf(pdf_file):
    """Validate an uploaded PDF file for size and format."""
    if pdf_file is None:
        return False, "No PDF file provided."
    if pdf_file.size > MAX_PDF_SIZE_BYTES:
        size_mb = round(pdf_file.size / (1024 * 1024), 2)
        return False, f"PDF size {size_mb}MB exceeds the 20MB limit."
    content_type = getattr(pdf_file, "content_type", "")
    if content_type not in {"application/pdf"}:
        return False, "Invalid file format. Only PDF files are allowed."
    _, ext = os.path.splitext(pdf_file.name)
    if ext.lower() != ".pdf":
        return False, "Invalid file extension. Only .pdf is allowed."
    return True, None


def upload_product_pdf(pdf_file, product_id, product_name, category_id, category_name):
    """Save a product PDF and return its media-relative path."""
    relative_folder = generate_product_image_folder(product_id, product_name, category_id, category_name)
    abs_folder = os.path.join(settings.MEDIA_ROOT, relative_folder)
    os.makedirs(abs_folder, exist_ok=True)
    filename = "product.pdf"
    abs_path = os.path.join(abs_folder, filename)
    with open(abs_path, "wb+") as dest:
        for chunk in pdf_file.chunks():
            dest.write(chunk)
    return os.path.join(relative_folder, filename).replace("\\", "/")