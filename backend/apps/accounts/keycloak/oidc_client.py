"""OIDC helpers for Keycloak (Authorization Code + PKCE, ID token verification)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from urllib.parse import urlencode

import requests
from authlib.jose import JsonWebKey, jwt
from authlib.jose.errors import JoseError

from .config import KeycloakConfig, issuer_matches

logger = logging.getLogger(__name__)

_jwks_cache: tuple[float, dict] = (0.0, {})


@dataclass
class OidcUserInfo:
    sub: str
    issuer: str
    email: str
    email_verified: bool
    preferred_username: str
    claims: dict


class OidcError(Exception):
    pass


def build_authorization_url(cfg: KeycloakConfig, *, state: str, nonce: str, code_challenge: str) -> str:
    base = cfg.base_url.rstrip("/")
    realm = cfg.realm
    auth_endpoint = f"{base}/realms/{realm}/protocol/openid-connect/auth"
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": cfg.scopes,
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{auth_endpoint}?{urlencode(params)}"


def _fetch_jwks(cfg: KeycloakConfig, *, force: bool = False) -> dict:
    global _jwks_cache
    now = time.time()
    if not force and _jwks_cache[1] and (now - _jwks_cache[0]) < 300:
        return _jwks_cache[1]
    resp = requests.get(cfg.jwks_uri, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _jwks_cache = (now, data)
    return data


def exchange_code_and_verify(
    cfg: KeycloakConfig,
    *,
    code: str,
    code_verifier: str,
    expected_nonce: str,
) -> OidcUserInfo:
    """Exchange authorization code for tokens and verify ID token."""
    token_url = f"{cfg.base_url.rstrip('/')}/realms/{cfg.realm}/protocol/openid-connect/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": cfg.client_id,
        "code": code,
        "redirect_uri": cfg.redirect_uri,
        "code_verifier": code_verifier,
    }
    if cfg.client_secret:
        data["client_secret"] = cfg.client_secret
    try:
        resp = requests.post(token_url, data=data, timeout=15)
    except requests.RequestException as exc:
        logger.warning("Keycloak token endpoint request failed: %s", exc)
        raise OidcError("KEYCLOAK_CODE_EXCHANGE_FAILED") from exc
    if resp.status_code != 200:
        logger.warning("Keycloak token exchange failed status=%s", resp.status_code)
        raise OidcError("KEYCLOAK_CODE_EXCHANGE_FAILED")
    payload = resp.json()
    id_token = payload.get("id_token")
    if not id_token:
        raise OidcError("KEYCLOAK_CLAIMS_INVALID")

    try:
        jwks = _fetch_jwks(cfg)
        key_set = JsonWebKey.import_key_set(jwks)
        claims = jwt.decode(id_token, key_set)
    except (JoseError, requests.RequestException, ValueError) as exc:
        logger.warning("ID token decode failed: %s", exc)
        # retry once with fresh JWKS
        try:
            jwks = _fetch_jwks(cfg, force=True)
            key_set = JsonWebKey.import_key_set(jwks)
            claims = jwt.decode(id_token, key_set)
        except Exception as exc2:
            logger.warning("ID token decode retry failed: %s", exc2)
            raise OidcError("KEYCLOAK_TOKEN_INVALID") from exc2

    try:
        claims.validate()
    except JoseError as exc:
        logger.warning("ID token validation failed: %s", exc)
        raise OidcError("KEYCLOAK_TOKEN_INVALID") from exc

    iss = claims.get("iss") or ""
    if not issuer_matches(cfg.issuer, iss):
        raise OidcError("KEYCLOAK_TOKEN_INVALID")

    aud = claims.get("aud")
    azp = claims.get("azp")
    aud_ok = False
    if aud == cfg.client_id:
        aud_ok = True
    elif isinstance(aud, list) and cfg.client_id in aud:
        aud_ok = True
    # If azp is present it must match the client
    if azp is not None and azp != cfg.client_id:
        raise OidcError("KEYCLOAK_TOKEN_INVALID")
    if not aud_ok:
        # Some Keycloak setups omit aud for public clients in some flows; allow if azp matches
        if azp == cfg.client_id:
            aud_ok = True
    if not aud_ok:
        raise OidcError("KEYCLOAK_TOKEN_INVALID")

    nonce = claims.get("nonce")
    if not nonce or nonce != expected_nonce:
        raise OidcError("KEYCLOAK_INVALID_NONCE")

    sub = claims.get("sub")
    if not sub:
        raise OidcError("KEYCLOAK_CLAIMS_INVALID")

    email = (claims.get("email") or "") if isinstance(claims.get("email"), str) else ""
    ev = claims.get("email_verified")
    if isinstance(ev, bool):
        email_verified = ev
    elif isinstance(ev, str):
        email_verified = ev.strip().lower() in ("true", "1", "yes")
    else:
        email_verified = False
    preferred = (claims.get("preferred_username") or "") if isinstance(claims.get("preferred_username"), str) else ""

    return OidcUserInfo(
        sub=str(sub),
        issuer=iss.rstrip("/"),
        email=email,
        email_verified=email_verified,
        preferred_username=preferred,
        claims=dict(claims),
    )
