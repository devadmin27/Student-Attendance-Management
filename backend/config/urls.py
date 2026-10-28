from django.urls import include, path
from django.contrib import admin

# Load our admin registrations (must import before admin.site.urls so all
# model admins are registered with the default admin site).
import admin_config  # noqa: F401  isort: skip

urlpatterns = [
    path("api/v1/", include("config.api_urls")),
    path("admin/", admin.site.urls),
]
