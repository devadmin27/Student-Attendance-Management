from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.leaves import views

router = DefaultRouter()
router.register("leave-requests", views.LeaveRequestViewSet, basename="leave-request")
router.register("leave-courses", views.LeaveCourseViewSet, basename="leave-course")

urlpatterns = [path("", include(router.urls))]
