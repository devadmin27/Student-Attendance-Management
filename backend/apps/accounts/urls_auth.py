from django.urls import path

from apps.accounts import views_auth
from apps.accounts import views_keycloak

urlpatterns = [
    path("login/", views_auth.LoginView.as_view(), name="auth-login"),
    path("refresh/", views_auth.RefreshView.as_view(), name="auth-refresh"),
    path("logout/", views_auth.LogoutView.as_view(), name="auth-logout"),
    path("me/", views_auth.MeView.as_view(), name="auth-me"),
    path("method/", views_keycloak.AuthMethodView.as_view(), name="auth-method"),
    path("keycloak/config/", views_keycloak.KeycloakConfigView.as_view(), name="auth-keycloak-config"),
    path("keycloak/login/", views_keycloak.KeycloakLoginView.as_view(), name="auth-keycloak-login"),
    path("keycloak/callback/", views_keycloak.KeycloakCallbackView.as_view(), name="auth-keycloak-callback"),
    path("keycloak/logout/", views_keycloak.KeycloakLogoutView.as_view(), name="auth-keycloak-logout"),
]
