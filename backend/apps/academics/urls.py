from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.academics import views

router = DefaultRouter()
router.register("programs", views.ProgramViewSet, basename="program")
router.register("class-groups", views.ClassGroupViewSet, basename="class-group")
router.register("academic-terms", views.AcademicTermViewSet, basename="academic-term")

urlpatterns = [path("", include(router.urls))]
