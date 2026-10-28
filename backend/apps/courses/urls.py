from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.courses import views

router = DefaultRouter()
router.register("courses", views.CourseViewSet, basename="course")
router.register("course-offerings", views.CourseOfferingViewSet, basename="course-offering")
router.register("enrollments", views.EnrollmentViewSet, basename="enrollment")

urlpatterns = [path("", include(router.urls))]
