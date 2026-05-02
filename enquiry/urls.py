from django.urls import path
from .views import (
    ContactUsCreateView,
    ContactUsListView,
    EnquiryListView,
    EnquiryCreateView,
    EnquiryDetailView,
    EnquiryUpdateView,
    EnquiryDeleteView,
)

app_name = "enquiry"

urlpatterns = [
    path("", EnquiryListView.as_view(), name="enquiry_list"),
    path("create/", EnquiryCreateView.as_view(), name="enquiry_create"),
    path("contact-us/", ContactUsCreateView.as_view(), name="contact_us_create"),
    path("contact-us/admin/", ContactUsListView.as_view(), name="contact_us_admin_list"),
    path("<int:pk>/", EnquiryDetailView.as_view(), name="enquiry_detail"),
    path("<int:pk>/update/", EnquiryUpdateView.as_view(), name="enquiry_update"),
    path("<int:pk>/delete/", EnquiryDeleteView.as_view(), name="enquiry_delete"),
]
