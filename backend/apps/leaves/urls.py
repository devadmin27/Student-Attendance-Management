from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.leaves import views

router = DefaultRouter()
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")
router.register("leave-courses", views.LeaveCourseViewSet, basename="leave-course")

urlpatterns = [
    # Explicit detail route so the printed A4 document can be served to
    # students, instructors, and admins with its own role-aware scoping.
    path(
        "leave-requests/<uuid:pk>/print/",
        views.LeaveRequestPrintView.as_view(),
        name="leave-request-print",
    ),
    path("", include(router.urls)),
]
