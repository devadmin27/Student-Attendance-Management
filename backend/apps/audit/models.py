"""Audit log — append-only. No edit/delete through the public API (spec §16)."""
import uuid

from django.conf import settings
from django.db import models


def client_ip(request) -> str:
    """Best-effort client IP for audit only. Behind proxies use X-Forwarded-For."""
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name="audit_logs", verbose_name="ผู้กระทำ",
    )
    action = models.CharField("การกระทำ", max_length=64, db_index=True)
    resource_type = models.CharField("ประเภททรัพยากร", max_length=64)
    resource_id = models.CharField("รหัสทรัพยากร", max_length=64, blank=True, default="")
    metadata = models.JSONField("ข้อมูลประกอบ", default=dict, blank=True)
    ip_address = models.GenericIPAddressField(
        "IP ผู้ใช้", null=True, blank=True,
        help_text="เก็บตามนโยบายความเป็นส่วนตัว (PDPA)",
    )
    user_agent = models.CharField("User Agent", max_length=300, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["actor", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.action} {self.resource_type} {self.resource_id}"


def log_audit(
    actor, action: str, resource_type: str, resource_id: str = "",
    metadata: dict | None = None, request=None,
) -> None:
    """Append an audit entry. Never stores tokens or passwords."""
    metadata = metadata or {}
    safe_meta = {k: v for k, v in metadata.items() if k not in {"password", "token", "qr"}}
    AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id or ""),
        metadata=safe_meta,
        ip_address=client_ip(request) or None,
        user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:300] if request else "",
    )
