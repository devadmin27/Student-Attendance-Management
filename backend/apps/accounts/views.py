"""Admin management endpoints: users, students, instructors, CSV import."""
import csv
import io

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from common.csvutils import sanitize_csv_value
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.accounts.models import StudentProfile, User, InstructorProfile
from apps.accounts.serializers import (
    InstructorProfileSerializer,
    StudentCreateSerializer,
    StudentProfileSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from apps.audit.models import log_audit
from apps.audit.throttles import CSVImportThrottle
from apps.attendance.models import AttendanceSession
from common.permissions import IsAdmin
from common.responses import success_response


class UserViewSet(viewsets.ModelViewSet):
    """Admin-only account management (SAMS spec §3.1)."""

    queryset = User.objects.all().select_related("student_profile", "instructor_profile")
    serializer_class = UserSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "role": ["exact"],
        "is_active": ["exact"],
    }
    search_fields = ["username", "email"]
    ordering_fields = ["username", "role", "date_joined", "is_active"]
    ordering = ["-date_joined"]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def destroy(self, request, *args, **kwargs):
        """Soft-style deletion: deactivate instead of deleting users that
        already have attendance history (referential integrity, spec §7.3)."""
        user = self.get_object()
        # Reverse OneToOne without an existing profile raises
        # RelatedObjectDoesNotExist (e.g. instructor accounts) — never 500.
        try:
            student_profile = user.student_profile
        except ObjectDoesNotExist:
            student_profile = None
        has_history = student_profile is not None and student_profile.attendance_records.exists()
        if getattr(request.user, "pk", None) == user.pk:
            return Response(
                {"success": False, "message": "ไม่สามารถลบบัญชีของตนเองได้", "code": "FORBIDDEN"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if has_history:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            log_audit(request.user, "user_deactivate", "user", user.pk, request=request)
            return success_response({"id": str(user.pk), "is_active": False},
                                    "มีประวัติการเข้าเรียน — ระงับบัญชีแทนการลบ")
        response = super().destroy(request, *args, **kwargs)
        log_audit(request.user, "user_delete", "user", kwargs.get("pk"), request=request)
        return response

    @action(detail=True, methods=["patch"], url_path="suspend")
    def suspend(self, request, pk=None):
        user = self.get_object()
        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        log_audit(request.user, "user_suspend", "user", user.pk, request=request)
        return success_response(UserSerializer(user).data, "ระงับบัญชีสำเร็จ")

    @action(detail=True, methods=["patch"], url_path="activate")
    def activate(self, request, pk=None):
        user = self.get_object()
        user.is_active = True
        user.save(update_fields=["is_active", "updated_at"])
        log_audit(request.user, "user_activate", "user", user.pk, request=request)
        return success_response(UserSerializer(user).data, "เปิดใช้งานบัญชีสำเร็จ")


class StudentProfileViewSet(viewsets.ModelViewSet):
    """Students list (+admin CRUD). Backend has all data; students scope
    their own data — never exposing cross-student info."""

    queryset = StudentProfile.objects.select_related(
        "user", "program", "class_group"
    )
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "program": ["exact"],
        "class_group": ["exact"],
        "academic_year_level": ["exact"],
        "status": ["exact"],
    }
    search_fields = ["student_code", "first_name", "last_name", "user__username"]
    ordering_fields = ["student_code", "first_name", "last_name", "academic_year_level"]
    ordering = ["student_code"]

    def get_serializer_class(self):
        if self.action == "create":
            return StudentCreateSerializer
        return StudentProfileSerializer

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        """Bulk student import from CSV (admin). Validates headers/values,
        creates account + profile atomically per row, reports row errors."""
        upload = request.FILES.get("file")
        if upload is None:
            return Response(
                {"success": False, "message": "กรุณาแนบไฟล์ CSV ชื่อ file", "code": "FILE_REQUIRED"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if upload.size > 2 * 1024 * 1024:
            return Response(
                {"success": False, "message": "ขนาดไฟล์เกิน 2MB", "code": "FILE_TOO_LARGE"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            text = upload.read().decode("utf-8-sig")
        except UnicodeDecodeError:
            return Response(
                {"success": False, "message": "ต้องเป็นไฟล์ CSV แบบ UTF-8", "code": "ENCODING_INVALID"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        reader = csv.DictReader(io.StringIO(text))
        required = {"username", "student_code", "first_name", "last_name", "password"}
        if not reader.fieldnames or not required.issubset({f.strip() for f in reader.fieldnames}):
            return Response(
                {
                    "success": False,
                    "message": f"ต้องมีคอลัมน์ {'  '.join(sorted(required))}",
                    "code": "CSV_HEADER_INVALID",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        created, errors = 0, []
        with transaction.atomic():
            for i, row in enumerate(reader, start=2):
                row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
                try:
                    username = row["username"]
                    code = row["student_code"]
                    password = row.get("password") or ""
                    if not username or not code or not password:
                        raise ValueError("username/student_code/password ต้องไม่ว่าง")
                    if User.objects.filter(username__iexact=username).exists() or \
                        StudentProfile.objects.filter(student_code=code).exists():
                        raise ValueError("มีบัญชีหรือรหัสนักศึกษานี้อยู่แล้ว")
                    user = User.objects.create_user(
                        username=username,
                        email=row.get("email", "") or "",
                        password=password,
                        role="student",
                    )
                    profile = user.student_profile
                    profile.student_code = code
                    # Sanitize free-text cells at import as well as export
                    # (defense in depth, spec §16): stops spreadsheet formula
                    # payloads like =HYPERLINK(...) ever entering the system.
                    profile.first_name = sanitize_csv_value(row["first_name"])
                    profile.last_name = sanitize_csv_value(row["last_name"])
                    profile.academic_year_level = int(row.get("academic_year_level") or 1)
                    profile.save()
                    created += 1
                except (ValueError, TypeError, KeyError) as exc:
                    errors.append({"row": i, "message": str(exc)})
        log_audit(
            request.user, "students_import", "student_profile",
            metadata={"created": created, "failed": len(errors)},
            request=request,
        )
        message = f"นำเข้าสำเร็จ {created} รายการ" + (f" ล้มเหลว {len(errors)} รายการ" if errors else "")
        return success_response({"created": created, "failed": errors}, message)


class InstructorProfileViewSet(viewsets.ModelViewSet):
    queryset = InstructorProfile.objects.select_related("user")
    serializer_class = InstructorProfileSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"status": ["exact"]}
    search_fields = ["employee_code", "first_name", "last_name", "user__username"]
    ordering_fields = ["employee_code", "first_name", "last_name"]
    ordering = ["employee_code"]

    def create(self, request, *args, **kwargs):
        payload = request.data
        to_create = {
            "username": payload.get("username") or payload.get("employee_code"),
            "email": payload.get("email", "") or "",
            "password": payload.get("password"),
            "employee_code": payload.get("employee_code"),
            "first_name": payload.get("first_name"),
            "last_name": payload.get("last_name"),
            "department": payload.get("department", ""),
        }
        if not (to_create["username"] and to_create["password"] and
                to_create["employee_code"] and to_create["first_name"] and to_create["last_name"]):
            return Response(
                {"success": False, "message": "กรุณาระบุข้อมูลให้ครบ: username/password/employee_code/first_name/last_name",
                 "code": "VALIDATION_ERROR"},
                status=400,
            )
        if User.objects.filter(username__iexact=to_create["username"]).exists() or \
            InstructorProfile.objects.filter(employee_code=to_create["employee_code"]).exists():
            return Response(
                {"success": False, "message": "มีบัญชีหรือรหัสพนักงานนี้อยู่แล้ว", "code": "DUPLICATE"},
                status=400,
            )
        from django.contrib.auth.password_validation import validate_password

        try:
            validate_password(to_create["password"])
        except Exception as exc:
            return Response(
                {"success": False, "message": "รหัสผ่านไม่ผ่านเกณฑ์: " + str(exc), "code": "PASSWORD_WEAK"},
                status=400,
            )
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=to_create["username"], email=to_create["email"],
                    password=to_create["password"], role="instructor",
                )
                # create_user already inserted the InstructorProfile via
                # UserManager._ensure_profile (employee_code=auto-...) — update
                # that row instead of inserting a second one for the same
                # OneToOne user_id (UniqueViolation on Postgres → 500).
                instance = InstructorProfile.objects.get(user=user)
                instance.employee_code = to_create["employee_code"]
                instance.first_name = to_create["first_name"]
                instance.last_name = to_create["last_name"]
                instance.department = to_create["department"]
                instance.save()
        except IntegrityError:
            return Response(
                {"success": False, "message": "มีบัญชีหรือรหัสพนักงานนี้อยู่แล้ว", "code": "DUPLICATE"},
                status=400,
            )
        log_audit(request.user, "instructor_create", "instructor_profile", instance.pk, request=request)
        return success_response(
            InstructorProfileSerializer(instance).data, "เพิ่มอาจารย์สำเร็จ", 201
        )
