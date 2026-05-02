from django.urls import path
from .views import (
    # Category — Admin
    api_admin_list_categories,
    api_admin_filter_sort_categories,
    api_add_category,
    api_view_category,
    api_update_category,
    api_delete_category,
    # Category — Public
    api_list_categories,
    api_filter_sort_categories,
    # SubCategory — Admin
    api_admin_list_subcategories,
    api_admin_filter_sort_subcategories,
    api_add_subcategory,
    api_view_subcategory,
    api_update_subcategory,
    api_delete_subcategory,
    # SubCategory — Public
    api_list_subcategories,
    api_filter_sort_subcategories,
    # Product — Admin
    api_admin_list_products,
    api_admin_filter_sort_products,
    api_add_product,
    api_view_product,
    api_update_product,
    api_delete_product,
    # Product — Public
    api_list_products,
    api_filter_sort_products,
    api_get_product,
    # Search
    api_search_suggestions,
    api_popular_products,
)

urlpatterns = [
    # ── Category — Public ──
    path('list/',                api_list_categories,         name='api-list-categories'),
    path('filter-sort/',         api_filter_sort_categories,  name='api-filter-sort-categories'),

    # ── Category — Admin CRUD ──
    path('admin/list/', api_admin_list_categories,   name='api-admin-list-categories'),
    path('admin/filter-sort/', api_admin_filter_sort_categories, name='api-admin-filter-sort-categories'),
    path('add/',  api_add_category, name='api-add-category'),
    path('view/<int:pk>/',  api_view_category, name='api-view-category'),
    path('update/<int:pk>/', api_update_category,name='api-update-category'),
    path('delete/<int:pk>/', api_delete_category, name='api-delete-category'),

    # ── SubCategory — Public ──
    path('subcategories/list/',              api_list_subcategories,         name='api-list-subcategories'),
    path('subcategories/filter-sort/',       api_filter_sort_subcategories,  name='api-filter-sort-subcategories'),

    # ── SubCategory — Admin CRUD ──
    path('subcategories/admin/list/', api_admin_list_subcategories, name='api-admin-list-subcategories'),
    path('subcategories/admin/filter-sort/', api_admin_filter_sort_subcategories, name='api-admin-filter-sort-subcategories'),
    path('subcategories/add/',  api_add_subcategory, name='api-add-subcategory'),
    path('subcategories/view/<int:pk>/',api_view_subcategory, name='api-view-subcategory'),
    path('subcategories/update/<int:pk>/',   api_update_subcategory,name='api-update-subcategory'),
    path('subcategories/delete/<int:pk>/',   api_delete_subcategory,name='api-delete-subcategory'),

    # ── Product — Public ──
    path('products/list/',               api_list_products,       name='api-list-products'),
    path('products/filter-sort/',        api_filter_sort_products, name='api-filter-sort-products'),
    path('products/popular/',            api_popular_products,    name='api-popular-products'),
    path('products/<int:pk>/',           api_get_product,         name='api-get-product'),

    # ── Search Suggestions ──
    path('search/suggestions/',          api_search_suggestions,  name='api-search-suggestions'),

    # ── Product — Admin CRUD ──
    path('products/admin/list/',         api_admin_list_products, name='api-admin-list-products'),
    path('products/admin/filter-sort/',  api_admin_filter_sort_products, name='api-admin-filter-sort-products'),
    path('products/add/',                api_add_product,         name='api-add-product'),
    path('products/view/<int:pk>/',      api_view_product,        name='api-view-product'),
    path('products/update/<int:pk>/',    api_update_product,      name='api-update-product'),
    path('products/delete/<int:pk>/',    api_delete_product,      name='api-delete-product'),
]

