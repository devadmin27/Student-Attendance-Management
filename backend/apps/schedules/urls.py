from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.schedules import views

router = DefaultRouter()
router.register("class-schedules", views.ClassScheduleViewSet, basename="class-schedule")

urlpatterns = [path("", include(router.urls))]
