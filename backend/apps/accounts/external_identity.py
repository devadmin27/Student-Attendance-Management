"""External identity mapping for OIDC providers (Keycloak, etc.).

Maps an external (issuer, subject) to a local SAMS User. Never used as the
sole auth source; SAMS role/is_active/policy remain authoritative.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ExternalIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
        verbose_name="บัญชีผู้ใช้",
    )
    provider = models.CharField("ผู้ให้บริการ", max_length=32, default="keycloak")
    issuer = models.URLField("Issuer", max_length=512)
    subject = models.CharField("Subject (sub)", max_length=255)
    email_at_link = models.EmailField("อีเมลตอนผูก", blank=True, default="")
    preferred_username = models.CharField("ชื่อผู้ใช้ที่ IdP", max_length=150, blank=True, default="")
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    last_login_at = models.DateTimeField("เข้าสู่ระบบล่าสุดผ่าน IdP", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="ผูกโดย",
    )

    class Meta:
        db_table = "external_identities"
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "subject"],
                name="uq_external_identity_issuer_subject",
            ),
        ]
        indexes = [
            models.Index(fields=["provider", "issuer"]),
        ]

    def __str__(self) -> str:
        return f"{self.provider}:{self.issuer}:{self.subject[:16]}…"
