from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.attendance import views

router = DefaultRouter()
router.register("attendance/sessions", views.AttendanceSessionViewSet, basename="attendance-session")
router.register("attendance/records", views.AttendanceRecordViewSet, basename="attendance-record")

urlpatterns = [
    path("", include(router.urls)),
    path("attendance/check-in/", views.CheckInView.as_view(), name="attendance-checkin"),
    path("attendance/my-history/", views.StudentMyHistoryView.as_view(), name="my-attendance-history"),
]
