"""Secure admin bootstrap command (spec §15: no fixed public passwords).

Usage:
  python manage.py create_admin --username admin1 --email admin@x.ac.th
  (password is prompted with confirmation — never passed via command line
   to avoid shell history leakage; or set SAMS_ADMIN_PASSWORD env var for
   scripted CI usage only)
"""
import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User


class Command(BaseCommand):
    help = "สร้างบัญชีผู้ดูแลระบบ (อย่าใช้รหัสผ่านสาธารณะตายตัว)"

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", default="")
        parser.add_argument(
            "--password-env",
            default="SAMS_ADMIN_PASSWORD",
            help="ชื่อ Environment Variable ที่เก็บรหัสผ่าน (สำหรับ CI เท่านั้น)",
        )

    def handle(self, *args, **options):
        username = options["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise CommandError(f"มีบัญชีชื่อผู้ใช้ '{username}' อยู่แล้ว")

        password_env = options["password_env"]
        import os

        password = os.environ.get(password_env, "")
        if not password:
            password = getpass.getpass("รหัสผ่านผู้ดูแลระบบ: ")
            confirm = getpass.getpass("ยืนยันรหัสผ่าน: ")
            if password != confirm:
                raise CommandError("รหัสผ่านไม่ตรงกัน ยกเลิกการสร้างบัญชี")

        try:
            validate_password(password)
        except ValidationError as exc:
            raise CommandError(
                "รหัสผ่านไม่ผ่านเกณฑ์ความปลอดภัย: " + "; ".join(exc.messages)
            )

        user = User.objects.create_user(
            username=username,
            email=options["email"],
            password=password,
            role="admin",
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(f"สร้างผู้ดูแลระบบ '{username}' สำเร็จ"))
