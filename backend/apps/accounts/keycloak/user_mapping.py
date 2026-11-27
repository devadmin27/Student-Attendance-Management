"""Map Keycloak identity (issuer, sub) to SAMS User."""
from __future__ import annotations

from django.utils import timezone

from apps.accounts.external_identity import ExternalIdentity


def find_user_by_keycloak_identity(issuer: str, subject: str):
    if not issuer or not subject:
        return None
    try:
        ei = (
            ExternalIdentity.objects.select_related("user")
            .filter(provider="keycloak", issuer=issuer.rstrip("/"), subject=subject)
            .first()
        )
    except Exception:
        return None
    if ei is None:
        return None
    ei.last_login_at = timezone.now()
    ei.save(update_fields=["last_login_at"])
    return ei.user
