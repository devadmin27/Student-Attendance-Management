# Generated for Keycloak external identity mapping (manual)
import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_student_status_vocabulary"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalIdentity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("provider", models.CharField(default="keycloak", max_length=32, verbose_name="ผู้ให้บริการ")),
                ("issuer", models.URLField(max_length=512, verbose_name="Issuer")),
                ("subject", models.CharField(max_length=255, verbose_name="Subject (sub)")),
                ("email_at_link", models.EmailField(blank=True, default="", max_length=254, verbose_name="อีเมลตอนผูก")),
                ("preferred_username", models.CharField(blank=True, default="", max_length=150, verbose_name="ชื่อผู้ใช้ที่ IdP")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="สร้างเมื่อ")),
                ("last_login_at", models.DateTimeField(blank=True, null=True, verbose_name="เข้าสู่ระบบล่าสุดผ่าน IdP")),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="ผูกโดย",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="external_identities",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="บัญชีผู้ใช้",
                    ),
                ),
            ],
            options={
                "db_table": "external_identities",
            },
        ),
        migrations.AddIndex(
            model_name="externalidentity",
            index=models.Index(fields=["provider", "issuer"], name="accounts_ex_provide_7e8f9a_idx"),
        ),
        migrations.AddConstraint(
            model_name="externalidentity",
            constraint=models.UniqueConstraint(
                fields=("issuer", "subject"),
                name="uq_external_identity_issuer_subject",
            ),
        ),
    ]
