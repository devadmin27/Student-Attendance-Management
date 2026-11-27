"""Keycloak / OIDC configuration from environment (server-only)."""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings


@dataclass(frozen=True)
class KeycloakConfig:
    enabled: bool
    base_url: str
    realm: str
    client_id: str
    client_secret: str
    redirect_uri: str
    issuer: str
    jwks_uri: str
    scopes: str
    end_session_on_logout: bool
    post_logout_redirect_uri: str
    frontend_base_url: str
    auto_link_by_verified_email: bool
    auto_link_allowed_domains: tuple[str, ...]


def get_keycloak_config() -> KeycloakConfig:
    enabled = bool(getattr(settings, "KEYCLOAK_ENABLED", False))
    base_url = (getattr(settings, "KEYCLOAK_BASE_URL", "") or "").rstrip("/")
    realm = getattr(settings, "KEYCLOAK_REALM", "") or ""
    client_id = getattr(settings, "KEYCLOAK_CLIENT_ID", "") or ""
    client_secret = getattr(settings, "KEYCLOAK_CLIENT_SECRET", "") or ""
    redirect_uri = getattr(settings, "KEYCLOAK_REDIRECT_URI", "") or ""
    issuer = (getattr(settings, "KEYCLOAK_ISSUER", "") or f"{base_url}/realms/{realm}").rstrip("/")
    jwks_uri = getattr(settings, "KEYCLOAK_JWKS_URI", "") or f"{issuer}/protocol/openid-connect/certs"
    scopes = getattr(settings, "KEYCLOAK_SCOPES", "openid profile email") or "openid profile email"
    end_session = bool(getattr(settings, "KEYCLOAK_END_SESSION_ON_LOGOUT", False))
    post_logout = getattr(settings, "KEYCLOAK_POST_LOGOUT_REDIRECT_URI", "") or ""
    frontend_base = (getattr(settings, "FRONTEND_BASE_URL", "") or "").rstrip("/")
    auto_link = bool(getattr(settings, "KEYCLOAK_AUTO_LINK_BY_VERIFIED_EMAIL", False))
    domains = getattr(settings, "KEYCLOAK_AUTO_LINK_ALLOWED_DOMAINS", []) or []
    if isinstance(domains, str):
        domains = [d.strip().lower() for d in domains.split(",") if d.strip()]
    auto_link_domains = tuple(str(d).strip().lower() for d in domains if str(d).strip())
    return KeycloakConfig(
        enabled=enabled,
        base_url=base_url,
        realm=realm,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        issuer=issuer,
        jwks_uri=jwks_uri,
        scopes=scopes,
        end_session_on_logout=end_session,
        post_logout_redirect_uri=post_logout,
        frontend_base_url=frontend_base,
        auto_link_by_verified_email=auto_link,
        auto_link_allowed_domains=auto_link_domains,
    )


def is_keycloak_configured(cfg: KeycloakConfig) -> bool:
    return bool(
        cfg.enabled
        and cfg.base_url
        and cfg.realm
        and cfg.client_id
        and cfg.redirect_uri
        and cfg.issuer
    )


def issuer_matches(expected: str, actual: str) -> bool:
    """Compare issuers tolerating trailing slash differences."""
    if not expected or not actual:
        return False
    return expected.rstrip("/") == actual.rstrip("/")


def safe_frontend_redirect(cfg: KeycloakConfig, next_path: str | None) -> str:
    """Return a safe absolute redirect URL to frontend callback."""
    base = cfg.frontend_base_url
    if not base:
        # Fallback: relative path (same-origin) — caller should validate in practice.
        path = next_path if next_path and next_path.startswith("/") else "/"
        return path
    path = "/auth/callback"
    if next_path and next_path.startswith("/"):
        # Allow only internal paths to avoid open redirect.
        return f"{base}{path}?next={_url_quote(next_path)}"
    return f"{base}{path}"


def _url_quote(s: str) -> str:
    from urllib.parse import quote

    return quote(s, safe="/?=&%")
