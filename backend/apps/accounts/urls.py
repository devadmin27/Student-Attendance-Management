"""URL routing per app."""
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts import views

router = DefaultRouter()
router.register("users", views.UserViewSet, basename="user")
router.register("students", views.StudentProfileViewSet, basename="student")
router.register("instructors", views.InstructorProfileViewSet, basename="instructor")

urlpatterns = [
    path(
        "users/import-students/",
        views.StudentProfileViewSet.as_view({"post": "import_csv"}),
    ),
    path("", include(router.urls)),
]
