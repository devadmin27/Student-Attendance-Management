"""Keycloak Admin API client (service account, client_credentials)."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import KeycloakConfig, get_keycloak_config

logger = logging.getLogger(__name__)

_admin_token_cache: tuple[float, str] = (0.0, "")


class KeycloakAdminError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.body = body


@dataclass(frozen=True)
class KeycloakAdminConfig:
    base_url: str
    realm: str
    client_id: str
    client_secret: str

    @property
    def token_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/realms/{self.realm}/protocol/openid-connect/token"

    @property
    def admin_users_base(self) -> str:
        return f"{self.base_url.rstrip('/')}/admin/realms/{self.realm}/users"


def get_keycloak_admin_config() -> KeycloakAdminConfig | None:
    from django.conf import settings

    cfg = get_keycloak_config()
    admin_id = (getattr(settings, "KEYCLOAK_ADMIN_CLIENT_ID", "") or "").strip()
    admin_secret = (getattr(settings, "KEYCLOAK_ADMIN_CLIENT_SECRET", "") or "").strip()
    if not (cfg.enabled and cfg.base_url and cfg.realm and admin_id and admin_secret):
        return None
    return KeycloakAdminConfig(
        base_url=cfg.base_url,
        realm=cfg.realm,
        client_id=admin_id,
        client_secret=admin_secret,
    )


def _fetch_admin_token(admin_cfg: KeycloakAdminConfig) -> str:
    global _admin_token_cache
    now = time.time()
    if _admin_token_cache[1] and (now - _admin_token_cache[0]) < 55:
        return _admin_token_cache[1]
    try:
        resp = requests.post(
            admin_cfg.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": admin_cfg.client_id,
                "client_secret": admin_cfg.client_secret,
            },
            timeout=20,
        )
    except requests.RequestException as exc:
        logger.warning("Keycloak admin token request failed: %s", exc)
        raise KeycloakAdminError("ไม่สามารถเชื่อมต่อ Keycloak Admin API ได้") from exc
    if resp.status_code != 200:
        logger.warning("Keycloak admin token failed status=%s", resp.status_code)
        raise KeycloakAdminError("ไม่สามารถยืนยันตัวตนกับ Keycloak Admin API ได้ (ตรวจสอบ client/secret)")
    payload = resp.json()
    token = payload.get("access_token")
    if not token:
        raise KeycloakAdminError("Keycloak Admin API ไม่ส่ง access token กลับมา")
    _admin_token_cache = (now, token)
    return token


def clear_admin_token_cache() -> None:
    global _admin_token_cache
    _admin_token_cache = (0.0, "")


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def create_realm_user(
    admin_cfg: KeycloakAdminConfig,
    *,
    username: str,
    email: str | None,
    first_name: str,
    last_name: str,
    password: str,
) -> str:
    """
    Create user in Keycloak realm. Returns Keycloak user id (sub).
    """
    token = _fetch_admin_token(admin_cfg)
    body: dict[str, Any] = {
        "username": username,
        "enabled": True,
        "emailVerified": True,
        "firstName": first_name or "",
        "lastName": last_name or "",
        "requiredActions": ["UPDATE_PASSWORD"],
        "credentials": [
            {
                "type": "password",
                "value": password,
                "temporary": True,
            }
        ],
    }
    if email:
        body["email"] = email
    try:
        resp = requests.post(
            admin_cfg.admin_users_base,
            json=body,
            headers=_auth_headers(token),
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.warning("Keycloak admin create user request failed: %s", exc)
        raise KeycloakAdminError("ไม่สามารถเชื่อมต่อ Keycloak Admin API ได้") from exc

    if resp.status_code == 409:
        raise KeycloakAdminError("มีผู้ใช้นี้อยู่ใน Keycloak แล้ว (username หรือ email ซ้ำ)")
    if resp.status_code not in (201, 204):
        detail = ""
        try:
            j = resp.json()
            detail = j.get("errorMessage") or j.get("error_description") or j.get("error") or str(j)
        except Exception:
            detail = (resp.text or "")[:200]
        logger.warning("Keycloak admin create user failed status=%s body=%s", resp.status_code, detail)
        if resp.status_code == 403:
            raise KeycloakAdminError(
                "สร้างผู้ใช้ใน Keycloak ไม่สำเร็จ: สิทธิ์ไม่พอ (HTTP 403). "
                "ตรวจสอบ Client sams-admin เปิด Service accounts roles แล้ว Assign role จาก client realm-management: "
                "manage-users, view-users, query-users และรีสตาร์ท Django หลังเปลี่ยนสิทธิ์",
                status_code=resp.status_code,
            )
        raise KeycloakAdminError(
            f"สร้างผู้ใช้ใน Keycloak ไม่สำเร็จ: {detail or resp.status_code}",
            status_code=resp.status_code,
        )

    loc = resp.headers.get("Location") or ""
    if loc.rstrip("/").endswith("/"):
        pass
    kc_user_id = loc.rstrip("/").rsplit("/", 1)[-1] if "/" in loc else ""
    if kc_user_id:
        return kc_user_id

    # Fallback: search by username
    try:
        q = requests.get(
            admin_cfg.admin_users_base,
            params={"username": username, "exact": "true"},
            headers={"Authorization": f"Bearer {token}"},
            timeout=20,
        )
        if q.status_code == 200:
            arr = q.json()
            if isinstance(arr, list) and arr:
                uid = arr[0].get("id")
                if uid:
                    return str(uid)
    except Exception as exc:
        logger.warning("Keycloak admin lookup user after create failed: %s", exc)

    raise KeycloakAdminError("สร้างผู้ใช้ใน Keycloak สำเร็จแต่ไม่พบ user id จากการตอบกลับ")
