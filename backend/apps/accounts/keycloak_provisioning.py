"""Provision SAMS users into Keycloak (Admin API) and link ExternalIdentity."""
from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.external_identity import ExternalIdentity
from apps.accounts.keycloak.admin_client import (
    KeycloakAdminError,
    create_realm_user,
    get_keycloak_admin_config,
)
from apps.accounts.keycloak.config import get_keycloak_config, is_keycloak_configured
from apps.audit.models import log_audit

logger = logging.getLogger(__name__)


class KeycloakProvisionError(Exception):
    def __init__(self, message: str, *, code: str = "KEYCLOAK_PROVISION_FAILED"):
        super().__init__(message)
        self.message = message
        self.code = code


def provision_sams_user_to_keycloak(
    *,
    sams_user,
    password_plain: str,
    first_name: str,
    last_name: str,
    email: str,
    request=None,
    source: str = "single",
    audit_row_index: int | None = None,
    audit_filename: str | None = None,
) -> ExternalIdentity:
    """
    Create user in Keycloak (Admin API) and create ExternalIdentity for this SAMS user.
    Must be called inside an appropriate transaction context depending on caller policy:
    - single: call inside transaction.atomic() so SAMS create can roll back if this fails.
    - csv row: create SAMS first (committed per row as per policy), then call this; on failure do not rollback SAMS.
    """
    kc_cfg = get_keycloak_config()
    if not is_keycloak_configured(kc_cfg):
        raise KeycloakProvisionError("Keycloak ยังไม่ได้ตั้งค่าให้พร้อมใช้งาน", code="KEYCLOAK_NOT_CONFIGURED")
    admin_cfg = get_keycloak_admin_config()
    if admin_cfg is None:
        raise KeycloakProvisionError(
            "ยังไม่ได้ตั้งค่า Keycloak Admin API (KEYCLOAK_ADMIN_CLIENT_ID/SECRET)",
            code="KEYCLOAK_ADMIN_NOT_CONFIGURED",
        )

    username = sams_user.username
    try:
        kc_user_id = create_realm_user(
            admin_cfg,
            username=username,
            email=(email or "").strip() or None,
            first_name=(first_name or "").strip(),
            last_name=(last_name or "").strip(),
            password=password_plain,
        )
    except KeycloakAdminError as exc:
        raise KeycloakProvisionError(exc.message, code="KEYCLOAK_ADMIN_ERROR") from exc

    issuer = (kc_cfg.issuer or "").rstrip("/")
    try:
        with transaction.atomic():
            ei, created = ExternalIdentity.objects.update_or_create(
                provider="keycloak",
                issuer=issuer,
                subject=kc_user_id,
                defaults={"user": sams_user, "last_login_at": timezone.now()},
            )
            # If it existed and pointed elsewhere, we still updated to this sams_user? No: subject unique.
            # But if someone else had this subject (impossible if we just created) or race, update_or_create sets user.
    except IntegrityError as exc:
        raise KeycloakProvisionError(
            "ไม่สามารถผูกบัญชี Keycloak กับ SAMS ได้ (ข้อมูลซ้ำหรือขัดแย้ง)",
            code="KEYCLOAK_LINK_CONFLICT",
        ) from exc

    meta: dict = {
        "provider": "keycloak",
        "issuer": issuer,
        "kc_user_id": kc_user_id,
        "source": source,
    }
    if audit_row_index is not None:
        meta["row_index"] = audit_row_index
    if audit_filename:
        meta["filename"] = audit_filename
    log_audit(
        actor=getattr(request, "user", None) if request is not None else None,
        action="user_keycloak_provisioned" if source == "single" else "user_keycloak_provisioned_csv_row",
        resource_type="user",
        resource_id=str(sams_user.id),
        request=request,
        metadata=meta,
    )
    return ei
