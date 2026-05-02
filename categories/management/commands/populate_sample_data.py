from django.core.management.base import BaseCommand
from categories.models import Category, Product, ProductImage
from decimal import Decimal
import json
import requests
import os
import re
from django.conf import settings


class Command(BaseCommand):
    help = 'Populate database with categories from media directory and sample products'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-token',
            type=str,
            help='JWT token for admin API access',
            required=True
        )

    def handle(self, *args, **options):
        admin_token = options['admin_token']
        self.stdout.write('Scanning media directory and syncing categories via admin API...')
        
        # Scan media directory for categories
        try:
            media_categories = self.scan_media_categories()
            self.stdout.write(f'Found {len(media_categories)} categories in media directory')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to scan media directory: {str(e)}'))
            return
        
        # Fetch existing categories from admin API
        try:
            existing_categories = self.fetch_categories_from_admin_api(admin_token)
            self.stdout.write(f'Found {len(existing_categories)} existing categories in database')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch categories from admin API: {str(e)}'))
            return
        
        # Create missing categories
        try:
            created_categories = self.create_missing_categories(media_categories, existing_categories, admin_token)
            self.stdout.write(f'Created {len(created_categories)} new categories')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to create categories: {str(e)}'))
            return
        
        # Fetch updated categories list
        try:
            all_categories = self.fetch_categories_from_admin_api(admin_token)
            category_mapping = self.map_categories_to_local(all_categories)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Failed to fetch updated categories: {str(e)}'))
            return
        
        # Create sample products
        if category_mapping:
            self.create_sample_products(category_mapping)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully processed {len(all_categories)} categories '
                f'and created sample products'
            )
        )

    def scan_media_categories(self):
        """Scan backend/media/category directory for available categories"""
        media_path = os.path.join(settings.BASE_DIR, 'media', 'category')
        categories = []
        
        if not os.path.exists(media_path):
            self.stdout.write(self.style.WARNING(f'Media directory not found: {media_path}'))
            return categories
        
        for item in os.listdir(media_path):
            item_path = os.path.join(media_path, item)
            if os.path.isdir(item_path) and item.startswith('category--'):
                # Parse category info from directory name
                # Format: category--01--footwears
                parts = item.split('--')
                if len(parts) >= 3:
                    category_id = parts[1]
                    category_name_slug = parts[2]
                    
                    # Convert slug to readable name
                    category_name = category_name_slug.replace('-', ' ').title()
                    
                    # Look for image file
                    image_url = None
                    for ext in ['webp', 'jpg', 'png', 'jpeg']:
                        image_file = os.path.join(item_path, f'image.{ext}')
                        if os.path.exists(image_file):
                            image_url = f'/media/category/{item}/image.{ext}'
                            break
                    
                    categories.append({
                        'directory': item,
                        'name': category_name,
                        'slug': category_name_slug,
                        'image_url': image_url,
                        'description': f'{category_name} for educational institutions'
                    })
                    
                    self.stdout.write(f'Found category: {category_name} ({item})')
        
        return categories

    def fetch_categories_from_admin_api(self, admin_token):
        """Fetch categories from the admin API"""
        api_url = 'http://127.0.0.1:8000/api/categories/admin/list/'
        headers = {
            'Authorization': f'Bearer {admin_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(api_url, headers=headers, params={'page_size': 100})
            response.raise_for_status()
            
            data = response.json()
            if data.get('message') == 'success' and data.get('data', {}).get('categories'):
                categories = data['data']['categories']
                return categories
            else:
                self.stdout.write(self.style.ERROR(f'Unexpected API response format: {data}'))
                return []
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'HTTP request failed: {str(e)}'))
            raise
        except json.JSONDecodeError as e:
            self.stdout.write(self.style.ERROR(f'Failed to parse JSON response: {str(e)}'))
            raise

    def create_missing_categories(self, media_categories, existing_categories, admin_token):
        """Create categories that exist in media but not in database"""
        existing_slugs = {cat.get('slug', '').lower() for cat in existing_categories}
        existing_names = {cat.get('name', '').lower() for cat in existing_categories}
        
        created_categories = []
        
        for media_cat in media_categories:
            media_slug = media_cat['slug'].lower()
            media_name = media_cat['name'].lower()
            
            # Check if category already exists by slug or name
            if media_slug not in existing_slugs and media_name not in existing_names:
                try:
                    created_cat = self.create_category_via_api(media_cat, admin_token)
                    if created_cat:
                        created_categories.append(created_cat)
                        self.stdout.write(f'Created category: {media_cat["name"]}')
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'Failed to create category {media_cat["name"]}: {str(e)}'))
            else:
                self.stdout.write(f'Category already exists: {media_cat["name"]}')
        
        return created_categories

    def create_category_via_api(self, category_data, admin_token):
        """Create a single category via admin API"""
        api_url = 'http://127.0.0.1:8000/api/categories/add/'
        headers = {
            'Authorization': f'Bearer {admin_token}',
        }
        
        # Prepare form data
        form_data = {
            'name': category_data['name'],
            'description': category_data['description'],
            'is_active': 'true',
            'is_featured': 'false',
            'display_order': '0'
        }
        
        try:
            response = requests.post(api_url, headers=headers, data=form_data)
            response.raise_for_status()
            
            result = response.json()
            if 'created successfully' in result.get('message', ''):
                return result.get('data', {}).get('category')
            else:
                self.stdout.write(self.style.ERROR(f'API error: {result}'))
                return None
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'HTTP request failed: {str(e)}'))
            return None

    def map_categories_to_local(self, admin_categories):
        """Map admin categories to local categories"""
        category_mapping = {}
        
        # Get all local categories
        local_categories = Category.objects.filter(deleted_at__isnull=True)
        local_cat_dict = {}
        
        # Create lookup dictionaries for local categories
        for local_cat in local_categories:
            local_cat_dict[local_cat.name.lower()] = local_cat
            if local_cat.slug:
                local_cat_dict[local_cat.slug.lower()] = local_cat
        
        # Map admin categories to local categories
        for admin_cat in admin_categories:
            admin_name = admin_cat.get('name', '').lower()
            admin_slug = admin_cat.get('slug', '').lower()
            
            local_category = None
            
            # Try to match by name first
            if admin_name in local_cat_dict:
                local_category = local_cat_dict[admin_name]
            # Try to match by slug
            elif admin_slug and admin_slug in local_cat_dict:
                local_category = local_cat_dict[admin_slug]
            
            if local_category:
                category_mapping[admin_cat['id']] = {
                    'admin_category': admin_cat,
                    'local_category': local_category
                }
        
        return category_mapping

    def create_sample_products(self, category_mapping):
        """Create sample products using the mapped categories"""
        products_data = [
            {
                'name': 'White School Shoes',
                'slug': 'white-school-shoes',
                'sku': 'FOOT-001',
                'short_description': 'Comfortable white leather school shoes for students',
                'long_description': 'High-quality white leather school shoes designed for comfort and durability. Perfect for daily school wear with non-slip soles.',
                'category_names': ['footwears', 'footwear', 'shoes'],
                'base_price': Decimal('1299.00'),
                'mrp': Decimal('1599.00'),
                'stock_quantity': 50,
                'brand': 'SchoolStep',
                'manufacturer': 'SchoolStep Industries',
                'specifications': [
                    {'key': 'Material', 'value': 'Genuine Leather'},
                    {'key': 'Color', 'value': 'White'},
                    {'key': 'Size', 'value': '6, 7, 8, 9, 10'},
                    {'key': 'Sole Type', 'value': 'Non-slip rubber'}
                ],
                'is_featured': True,
                'product_status': 'active',
                'images': [
                    '/media/category/category--01--footwears/products/product--01--white-shirt/image_02.jpg',
                    '/media/category/category--01--footwears/products/product--01--white-shirt/image_03.jpg'
                ]
            },
            {
                'name': 'Trimax Ball Pen Set',
                'slug': 'trimax-ball-pen-set',
                'sku': 'WRITE-001',
                'short_description': 'Premium ball pen set for smooth writing experience',
                'long_description': 'Professional grade ball pen set with smooth ink flow and comfortable grip. Perfect for students and professionals.',
                'category_names': ['writing instruments', 'pens', 'stationery'],
                'base_price': Decimal('299.00'),
                'mrp': Decimal('399.00'),
                'stock_quantity': 100,
                'brand': 'Trimax',
                'manufacturer': 'Trimax Writing Solutions',
                'specifications': [
                    {'key': 'Type', 'value': 'Ball Pen'},
                    {'key': 'Ink Color', 'value': 'Blue, Black'},
                    {'key': 'Pack Size', 'value': '10 pens'},
                    {'key': 'Tip Size', 'value': '0.7mm'}
                ],
                'is_new_arrival': True,
                'product_status': 'active',
                'images': [
                    '/media/category/category--02--writing-instruments/products/product--02--trimax/image_03.webp'
                ]
            },
            {
                'name': 'School Backpack',
                'slug': 'school-backpack',
                'sku': 'BAG-001',
                'short_description': 'Durable school backpack with multiple compartments',
                'long_description': 'High-quality school backpack designed for students with multiple compartments for books, laptop, and accessories.',
                'category_names': ['school bags backpacks', 'bags', 'backpacks'],
                'base_price': Decimal('899.00'),
                'mrp': Decimal('1199.00'),
                'stock_quantity': 40,
                'brand': 'StudyBag',
                'manufacturer': 'StudyBag Industries',
                'specifications': [
                    {'key': 'Material', 'value': 'Polyester'},
                    {'key': 'Color', 'value': 'Navy Blue, Black'},
                    {'key': 'Capacity', 'value': '25 Liters'},
                    {'key': 'Compartments', 'value': '3 main + 2 side pockets'}
                ],
                'product_status': 'active',
                'images': []
            },
            {
                'name': 'Student Notebook Set',
                'slug': 'student-notebook-set',
                'sku': 'NOTE-001',
                'short_description': 'Premium quality notebooks for students',
                'long_description': 'High-quality ruled notebooks perfect for students. Made with eco-friendly paper and durable binding.',
                'category_names': ['notebooks exercise books', 'notebooks', 'stationery'],
                'base_price': Decimal('199.00'),
                'mrp': Decimal('299.00'),
                'stock_quantity': 200,
                'brand': 'EduWrite',
                'manufacturer': 'EduWrite Stationery',
                'specifications': [
                    {'key': 'Pages', 'value': '200 pages'},
                    {'key': 'Paper Type', 'value': 'Ruled'},
                    {'key': 'Size', 'value': 'A4'},
                    {'key': 'Pack Size', 'value': '5 notebooks'}
                ],
                'product_status': 'active',
                'images': []
            },
            {
                'name': 'Art & Craft Kit',
                'slug': 'art-craft-kit',
                'sku': 'ART-001',
                'short_description': 'Complete art and craft kit for creative activities',
                'long_description': 'Comprehensive art and craft kit containing colors, brushes, papers, and other materials for creative projects.',
                'category_names': ['art craft materials', 'art', 'craft', 'creative'],
                'base_price': Decimal('599.00'),
                'mrp': Decimal('799.00'),
                'stock_quantity': 60,
                'brand': 'CreativeKids',
                'manufacturer': 'CreativeKids Arts',
                'specifications': [
                    {'key': 'Contents', 'value': 'Colors, Brushes, Papers, Glue'},
                    {'key': 'Age Group', 'value': '5-15 years'},
                    {'key': 'Kit Size', 'value': 'Large'},
                    {'key': 'Projects', 'value': '20+ activities'}
                ],
                'product_status': 'active',
                'images': []
            }
        ]
        
        # Create products with flexible category matching
        for product_data in products_data:
            category_names = product_data.pop('category_names', [])
            images = product_data.pop('images', [])
            
            # Find matching category
            matched_category = None
            for admin_id, mapping in category_mapping.items():
                admin_cat = mapping['admin_category']
                local_cat = mapping['local_category']
                
                admin_name_lower = admin_cat['name'].lower()
                admin_slug_lower = admin_cat.get('slug', '').lower()
                
                for cat_name in category_names:
                    if (cat_name.lower() in admin_name_lower or 
                        admin_name_lower in cat_name.lower() or
                        cat_name.lower() == admin_slug_lower):
                        matched_category = local_cat
                        self.stdout.write(f'Matched product "{product_data["name"]}" to category "{admin_cat["name"]}"')
                        break
                
                if matched_category:
                    break
            
            if not matched_category and category_mapping:
                # Use first available category as fallback
                first_mapping = next(iter(category_mapping.values()))
                matched_category = first_mapping['local_category']
                self.stdout.write(f'Using fallback category "{matched_category.name}" for product "{product_data["name"]}"')
            
            if matched_category:
                product_data['category'] = matched_category
                
                # Create or get the product
                product, created = Product.objects.get_or_create(
                    sku=product_data['sku'],
                    defaults=product_data
                )
                
                if created:
                    self.stdout.write(f'Created product: {product.name} in category: {matched_category.name}')
                    
                    # Create product images
                    for i, image_url in enumerate(images):
                        ProductImage.objects.create(
                            product=product,
                            image_url=image_url,
                            display_order=i,
                            is_primary=(i == 0)
                        )
                else:
                    self.stdout.write(f'Product already exists: {product.name}')