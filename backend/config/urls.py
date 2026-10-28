from django.urls import include, path
from django.contrib import admin

urlpatterns = [
    path("api/v1/", include("config.api_urls")),
    path("admin/", admin.site.urls),
]
