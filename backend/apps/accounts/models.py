"""User and profile models: accounts + student/instructor profiles."""
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone

ROLE_CHOICES = (
    ("admin", "ผู้ดูแลระบบ"),
    ("instructor", "อาจารย์ผู้สอน"),
    ("student", "นักศึกษา"),
)

PROFILE_STATUS_CHOICES = (
    ("active", "ใช้งานอยู่"),
    ("suspended", "ระงับการใช้งาน"),
    ("inactive", "ไม่ใช้งาน"),
)


class UserManager(BaseUserManager):
    """Custom manager: username-less counting, Thai-first roles."""

    def create_user(self, username, email=None, password=None, role="student", **extra):
        if not username:
            raise ValueError("ต้องระบุชื่อผู้ใช้ (username)")
        user = self.model(
            username=username,
            email=self.normalize_email(email) if email else "",
            role=role,
            **extra,
        )
        user.set_password(password)
        user.save(using=self._db)
        self._ensure_profile(user)
        return user

    @staticmethod
    def _ensure_profile(user: "User") -> None:
        from apps.accounts.models import InstructorProfile, StudentProfile

        # "auto-" + full UUID is 41 chars, exceeding max_length=32; Postgres
        # enforces the limit (SQLite silently allowed it and masked the bug).
        # A 12-char UUID hex slice gives a unique-enough fallback code.
        short = getattr(user, "pk", None)
        code = f"auto-{short.hex[:12]}" if hasattr(short, "hex") else f"auto-{uuid.uuid4().hex[:12]}"
        if user.role == "student":
            StudentProfile.objects.get_or_create(
                user=user,
                defaults={
                    "student_code": code,
                    "first_name": user.username,
                    "last_name": "",
                },
            )
        elif user.role == "instructor":
            InstructorProfile.objects.get_or_create(
                user=user,
                defaults={
                    "employee_code": code,
                    "first_name": user.username,
                    "last_name": "",
                },
            )

    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault("role", "admin")
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(username, email, password, role="admin", **extra)


class User(AbstractUser):
    """SAMS custom user: UUID PK + explicit system role (RBAC source of truth)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("อีเมล", blank=True, default="")
    role = models.CharField("บทบาทในระบบ", max_length=16, choices=ROLE_CHOICES, db_index=True)
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    created_at = models.DateTimeField("สร้างเมื่อ", auto_now_add=True)
    updated_at = models.DateTimeField("แก้ไขล่าสุด", auto_now=True)

    objects = UserManager()

    REQUIRED_FIELDS = ["email"]

    class Meta:
        db_table = "users"
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["role", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["email"],
                condition=~models.Q(email=""),
                name="uniq_user_email_when_set",
            )
        ]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class StudentProfile(models.Model):
    """Student academic identity. One-to-one with user account."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="student_profile", verbose_name="บัญชีผู้ใช้"
    )
    student_code = models.CharField(
        "รหัสนักศึกษา", max_length=32, unique=True
    )
    first_name = models.CharField("ชื่อ", max_length=100)
    last_name = models.CharField("นามสกุล", max_length=100)
    program = models.ForeignKey(
        "academics.Program", on_delete=models.PROTECT, null=True, blank=True,
        related_name="students", verbose_name="หลักสูตร",
    )
    academic_year_level = models.PositiveSmallIntegerField("ชั้นปี", default=1)
    class_group = models.ForeignKey(
        "academics.ClassGroup", on_delete=models.PROTECT, null=True, blank=True,
        related_name="students", verbose_name="กลุ่มเรียน",
    )
    status = models.CharField(
        "สถานะ", max_length=16, choices=PROFILE_STATUS_CHOICES, default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "student_profiles"
        ordering = ["student_code"]

    def __str__(self):
        return f"{self.student_code} {self.first_name} {self.last_name}"


class InstructorProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="instructor_profile", verbose_name="บัญชีผู้ใช้"
    )
    employee_code = models.CharField("รหัสพนักงาน", max_length=32, unique=True)
    first_name = models.CharField("ชื่อ", max_length=100)
    last_name = models.CharField("นามสกุล", max_length=100)
    department = models.CharField("ภาควิชา/สาขา", max_length=150, blank=True, default="")
    status = models.CharField(
        "สถานะ", max_length=16, choices=PROFILE_STATUS_CHOICES, default="active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "instructor_profiles"
        ordering = ["employee_code"]

    def __str__(self):
        return f"{self.employee_code} {self.first_name} {self.last_name}"
