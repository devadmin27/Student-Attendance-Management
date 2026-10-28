"""Root API URL configuration (versioned /api/v1/)."""
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from common.health import HealthCheckView
from apps.dashboard.views import (
    AdminDashboardView,
    InstructorDashboardView,
    StudentDashboardView,
)

urlpatterns = [
    # OpenAPI documentation
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    # Health check (no auth; DB ping included)
    path("health/", HealthCheckView.as_view(), name="health"),
    # Dashboards
    path("dashboard/admin/", AdminDashboardView.as_view(), name="dashboard-admin"),
    path("dashboard/instructor/", InstructorDashboardView.as_view(), name="dashboard-instructor"),
    path("dashboard/student/", StudentDashboardView.as_view(), name="dashboard-student"),
    # Domain routers
    path("auth/", include("apps.accounts.urls_auth")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.academics.urls")),
    path("", include("apps.courses.urls")),
    path("", include("apps.schedules.urls")),
    path("", include("apps.attendance.urls")),
    path("", include("apps.reports.urls")),
    path("", include("apps.audit.urls")),
]

