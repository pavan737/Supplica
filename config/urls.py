"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenRefreshView

from identity.views import (
    RoleListView, RoleCreateView, RoleUpdateView, RoleDeleteView,
    PermissionListView,
    AdminUserListView, AdminUserCreateView, AdminUserUpdateView, AdminUserDeleteView,
)

urlpatterns = [
    path('admin/', admin.site.urls),

    # SimpleJWT token refresh
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Identity app — Register & Login APIs
    path('api/', include('identity.urls')),

    # Categories, SubCategories & Products
    path('api/categories/', include('categories.urls')),

    # Enquiry CRUD
    path('api/enquiries/', include('enquiry.urls')),

    # ── Role management ──
    path('api/roles/', RoleListView.as_view(), name='role_list'),
    path('api/roles/create/', RoleCreateView.as_view(), name='role_create'),
    path('api/roles/<int:pk>/update/', RoleUpdateView.as_view(), name='role_update'),
    path('api/roles/<int:pk>/delete/', RoleDeleteView.as_view(), name='role_delete'),

    # ── Permission list ──
    path('api/permissions/', PermissionListView.as_view(), name='permission_list'),

    # ── Admin user management ──
    path('api/users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('api/users/create/', AdminUserCreateView.as_view(), name='admin_user_create'),
    path('api/users/<int:pk>/update/', AdminUserUpdateView.as_view(), name='admin_user_update'),
    path('api/users/<int:pk>/delete/', AdminUserDeleteView.as_view(), name='admin_user_delete'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
