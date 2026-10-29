from django.urls import include, path
from django.contrib import admin

# Load our admin registrations (must import before admin.site.urls so all
# model admins are registered with the default admin site).
import admin_config  # noqa: F401  isort: skip

urlpatterns = [
    path("api/v1/", include("config.api_urls")),
    # Django admin lives under /django-admin/ so that /admin/* stays free for
    # the Next.js frontend routes (/admin/dashboard, /admin/users, ...) — the
    # production nginx shared-domain proxy routes /admin/ to the frontend.
    path("django-admin/", admin.site.urls),
]
