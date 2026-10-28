from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.accounts import views_auth

urlpatterns = [
    path("login/", views_auth.LoginView.as_view(), name="auth-login"),
    path("refresh/", views_auth.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views_auth.LogoutView.as_view(), name="auth-logout"),
    path("me/", views_auth.MeView.as_view(), name="auth-me"),
]
