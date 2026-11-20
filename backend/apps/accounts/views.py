"""Admin management endpoints: users, students, instructors, CSV import."""
import csv
import io
from uuid import UUID

from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from django_filters.rest_framework import DjangoFilterBackend

from common.csvutils import sanitize_csv_value
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from apps.accounts.models import (
    MAX_ACADEMIC_YEAR_LEVEL,
    InstructorProfile,
    StudentProfile,
    User,
)
from apps.academics.models import ClassGroup, Program
from apps.accounts.serializers import (
    InstructorProfileSerializer,
    StudentCreateSerializer,
    StudentProfileSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from apps.audit.models import log_audit
from apps.accounts.services import apply_promotion
from apps.audit.throttles import CSVImportThrottle, PromotionThrottle
from apps.attendance.models import AttendanceSession
from common.permissions import AdminOnly, IsAdmin, IsAdminOrInstructor, RoleRequired
from common.responses import error_response, success_response

WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}
PROMOTION_ACTIONS = {"promote_group", "promote_selected"}
MAX_PROMOTION_BATCH = 200


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
        try:
            response = super().destroy(request, *args, **kwargs)
        except ProtectedError:
            # Append-only audit logs (actor on_delete=PROTECT) keep referring
            # to this account — hard delete is impossible by design; fall
            # back to the documented soft-delete instead of a 500.
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            log_audit(request.user, "user_deactivate", "user", user.pk, request=request)
            return success_response(
                {"id": str(user.pk), "is_active": False},
                "บัญชีถูกอ้างอิงโดยบันทึก audit — ระงับบัญชีแทนการลบ",
            )
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
    their own data — never exposing cross-student info.

    Instructors may READ students they plausibly teach (those in the class
    groups of their offerings, or enrolled in their offerings) for the
    enrollment/students pickers; every mutating action stays admin-only."""

    queryset = StudentProfile.objects.select_related(
        "user", "program", "class_group"
    )
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
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

    def get_permissions(self):
        if (
            self.action in WRITE_ACTIONS
            or self.action in PROMOTION_ACTIONS
            or self.action == "import_csv"
        ):
            return [AdminOnly()]
        return super().get_permissions()

    def get_throttles(self):
        if self.action in PROMOTION_ACTIONS:
            return [PromotionThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                return qs.none()
            from apps.courses.models import CourseOffering
            from django.db.models import Q

            own = CourseOffering.objects.filter(
                Q(instructor=profile) | Q(instructors=profile)
            )
            self_group_ids = own.values_list("class_group_id", flat=True)
            return qs.filter(
                Q(class_group_id__in=list(self_group_ids))
                | Q(enrollments__course_offering__in=own)
            ).distinct()
        return qs

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

        # ขอบเขตของชุดนำเข้า: หลักสูตร + กลุ่มเรียนที่เลือกจาก modal หน้า /students
        program, class_group = None, None
        program_id = str(request.data.get("program") or "").strip()
        class_group_id = str(request.data.get("class_group") or "").strip()
        try:
            if program_id:
                program = Program.objects.filter(pk=program_id).first()
                if program is None:
                    return Response(
                        {"success": False, "message": "ไม่พบหลักสูตรที่เลือก", "code": "PROGRAM_NOT_FOUND"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            if class_group_id:
                class_group = (
                    ClassGroup.objects.select_related("program").filter(pk=class_group_id).first()
                )
                if class_group is None:
                    return Response(
                        {"success": False, "message": "ไม่พบกลุ่มเรียนที่เลือก", "code": "CLASS_GROUP_NOT_FOUND"},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if program is not None and class_group.program_id != program.pk:
                    return Response(
                        {
                            "success": False,
                            "message": "กลุ่มเรียนที่เลือกไม่ได้อยู่ในหลักสูตรที่เลือก",
                            "code": "CLASS_GROUP_PROGRAM_MISMATCH",
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                program = program or class_group.program
        except (DjangoValidationError, ValueError):
            return Response(
                {
                    "success": False,
                    "message": "รหัสหลักสูตรหรือกลุ่มเรียนไม่ถูกต้อง",
                    "code": "IMPORT_SCOPE_INVALID",
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
                    if program is not None:
                        profile.program = program
                    if class_group is not None:
                        profile.class_group = class_group
                    default_year = class_group.academic_year_level if class_group else 1
                    year = int(row.get("academic_year_level") or default_year)
                    if not 1 <= year <= MAX_ACADEMIC_YEAR_LEVEL:
                        raise ValueError(
                            f"ชั้นปีต้องอยู่ระหว่าง 1–{MAX_ACADEMIC_YEAR_LEVEL}"
                        )
                    profile.academic_year_level = year
                    profile.save()
                    created += 1
                except (ValueError, TypeError, KeyError) as exc:
                    errors.append({"row": i, "message": str(exc)})
        log_audit(
            request.user, "students_import", "student_profile",
            metadata={
                "created": created,
                "failed": len(errors),
                "program": str(program.pk) if program else None,
                "class_group": str(class_group.pk) if class_group else None,
            },
            request=request,
        )
        message = f"นำเข้าสำเร็จ {created} รายการ" + (f" ล้มเหลว {len(errors)} รายการ" if errors else "")
        return success_response({"created": created, "failed": errors}, message)

    # -- Year-level promotion ------------------------------------------------
    def _promotion_common(self, request):
        reason = str(request.data.get("reason", "") or "").strip()[:500]
        if not reason:
            return None, error_response(
                "กรุณาระบุเหตุผลการเลื่อนชั้น", "REASON_REQUIRED", 400
            )
        if "to_year" in request.data:
            return None, error_response(
                "ระบบเลื่อนชั้นปีละ 1 ชั้นเท่านั้น", "TARGET_YEAR_NOT_SUPPORTED", 400
            )
        dry_run = str(request.data.get("dry_run", False)).lower() in {"1", "true", "yes"}
        return (reason, dry_run), None

    @staticmethod
    def _promotion_message(payload, label):
        message = f"{label}สำเร็จ {payload['succeeded']} รายการ"
        if payload["skipped"]:
            message += f" · ข้าม {payload['skipped']} รายการ"
        if payload["failed"]:
            message += f" · ไม่สำเร็จ {payload['failed']} รายการ"
        if payload["dry_run"]:
            message = f"ตัวอย่าง (ยังไม่บันทึก) — {message}"
        return message

    @action(detail=False, methods=["post"], url_path="promote-group")
    def promote_group(self, request):
        """Promote every student in matching class groups (+ the groups themselves)."""
        common, error = self._promotion_common(request)
        if error:
            return error
        reason, dry_run = common
        try:
            from_year = int(request.data.get("from_year"))
        except (TypeError, ValueError):
            return error_response("กรุณาระบุชั้นปีปัจจุบัน", "FROM_YEAR_REQUIRED", 400)
        if not 1 <= from_year <= MAX_ACADEMIC_YEAR_LEVEL:
            return error_response(
                f"ชั้นปีต้องอยู่ระหว่าง 1–{MAX_ACADEMIC_YEAR_LEVEL}", "INVALID_YEAR", 400
            )
        program_id = str(request.data.get("program") or "").strip()
        class_group_id = str(request.data.get("class_group") or "").strip()
        if not program_id and not class_group_id:
            return error_response("กรุณาเลือกหลักสูตรหรือกลุ่มเรียน", "SCOPE_REQUIRED", 400)

        with transaction.atomic():
            try:
                if class_group_id:
                    group = (
                        ClassGroup.objects.select_related("program")
                        .filter(pk=class_group_id).first()
                    )
                    if group is None:
                        return error_response("ไม่พบกลุ่มเรียนที่ระบุ", "CLASS_GROUP_NOT_FOUND", 400)
                    if group.academic_year_level != from_year:
                        return error_response(
                            "ชั้นปีของกลุ่มเรียนไม่ตรงกับชั้นปีที่ระบุ", "CLASS_GROUP_YEAR_MISMATCH", 400
                        )
                    if program_id and str(group.program_id) != program_id:
                        return error_response(
                            "กลุ่มเรียนที่เลือกไม่ได้อยู่ในหลักสูตรที่เลือก",
                            "CLASS_GROUP_PROGRAM_MISMATCH", 400,
                        )
                    groups = [group]
                    program = group.program
                else:
                    program = Program.objects.filter(pk=program_id).first()
                    if program is None:
                        return error_response("ไม่พบหลักสูตรที่ระบุ", "PROGRAM_NOT_FOUND", 400)
                    groups = list(
                        ClassGroup.objects.filter(
                            program=program, academic_year_level=from_year
                        ).select_for_update()
                    )
                    if not groups:
                        return error_response(
                            "ไม่พบกลุ่มเรียนในชั้นปีที่ระบุ", "NO_CLASS_GROUP", 400
                        )
                students = list(
                    StudentProfile.objects.filter(class_group__in=groups)
                    .select_for_update(of=("self",))
                    .select_related("class_group")
                    .order_by("student_code")
                )
            except (DjangoValidationError, ValueError, TypeError):
                return error_response("รหัสหลักสูตรหรือกลุ่มเรียนไม่ถูกต้อง", "SCOPE_INVALID", 400)
            if not students:
                return error_response("ไม่พบนักศึกษาในกลุ่มเรียนที่ระบุ", "NO_STUDENTS", 400)

            payload = apply_promotion(
                students=students,
                expected_years={student.pk: from_year for student in students},
                groups=groups,
                actor=request.user,
                request=request,
                mode="group",
                reason=reason,
                scope={
                    "program": str(program.pk),
                    "from_year": from_year,
                    "class_group": class_group_id or None,
                },
                dry_run=dry_run,
            )
        return success_response(payload, self._promotion_message(payload, "เลื่อนชั้นกลุ่มเรียน"))

    @action(detail=False, methods=["post"], url_path="promote-selected")
    def promote_selected(self, request):
        """Promote the chosen students only; class groups stay untouched."""
        common, error = self._promotion_common(request)
        if error:
            return error
        reason, dry_run = common
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return error_response("กรุณาเลือกนักศึกษาอย่างน้อย 1 รายการ", "INVALID_IDS", 400)
        if len(raw_ids) > MAX_PROMOTION_BATCH:
            return error_response(
                f"เลือกได้ครั้งละไม่เกิน {MAX_PROMOTION_BATCH} รายการ", "BATCH_TOO_LARGE", 400
            )
        try:
            ids = list(dict.fromkeys(UUID(str(value)) for value in raw_ids))
        except (TypeError, ValueError, AttributeError):
            return error_response("มีรหัสนักศึกษาที่ไม่ถูกต้อง", "INVALID_IDS", 400)

        raw_expected = request.data.get("expected_years")
        expected = {}
        if isinstance(raw_expected, dict):
            try:
                for key, value in raw_expected.items():
                    year = int(value)
                    if not 1 <= year <= MAX_ACADEMIC_YEAR_LEVEL:
                        raise ValueError(year)
                    expected[UUID(str(key))] = year
            except (TypeError, ValueError, AttributeError):
                return error_response(
                    "ข้อมูลชั้นปีที่คาดหวังไม่ถูกต้อง", "INVALID_EXPECTED_YEAR", 400
                )
        else:
            try:
                from_year = int(request.data.get("from_year"))
            except (TypeError, ValueError):
                return error_response(
                    "กรุณาระบุชั้นปีปัจจุบันหรือชั้นปีที่คาดหวัง", "FROM_YEAR_REQUIRED", 400
                )
            if not 1 <= from_year <= MAX_ACADEMIC_YEAR_LEVEL:
                return error_response(
                    f"ชั้นปีต้องอยู่ระหว่าง 1–{MAX_ACADEMIC_YEAR_LEVEL}", "INVALID_YEAR", 400
                )
            expected = {pk: from_year for pk in ids}
        for pk in ids:
            expected.setdefault(pk, -1)  # missing expectation -> YEAR_MISMATCH

        with transaction.atomic():
            scoped = {
                student.pk: student
                for student in (
                    StudentProfile.objects.filter(pk__in=ids)
                    .select_for_update(of=("self",))
                )
            }
            ordered = [scoped[pk] for pk in ids if pk in scoped]
            missing = [pk for pk in ids if pk not in scoped]
            if not ordered:
                return error_response(
                    "ไม่พบนักศึกษาที่เลือกหรือไม่มีสิทธิ์จัดการ", "NO_STUDENTS", 400
                )
            payload = apply_promotion(
                students=ordered,
                expected_years=expected,
                actor=request.user,
                request=request,
                mode="selected",
                reason=reason,
                scope={"requested": len(ids), "class_group": False},
                dry_run=dry_run,
            )
            if missing:
                payload["results"].extend(
                    {
                        "id": str(pk), "student_code": "", "student_name": "",
                        "from_year": None, "to_year": None,
                        "ok": False, "skipped": False,
                        "code": "NOT_FOUND", "message": "ไม่พบนักศึกษาหรือไม่มีสิทธิ์จัดการ",
                    }
                    for pk in missing
                )
                payload["requested"] = len(ids)
                payload["failed"] += len(missing)
        return success_response(payload, self._promotion_message(payload, "เลื่อนชั้นที่เลือก"))


class InstructorProfileViewSet(viewsets.ModelViewSet):
    """Instructors list — admin CRUD; instructors may READ (option pickers
    for co-instructor selection on their management pages)."""

    queryset = InstructorProfile.objects.select_related("user")
    serializer_class = InstructorProfileSerializer
    permission_classes = [IsAdminOrInstructor]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"status": ["exact"]}
    search_fields = ["employee_code", "first_name", "last_name", "user__username"]
    ordering_fields = ["employee_code", "first_name", "last_name"]
    ordering = ["employee_code"]

    def get_permissions(self):
        if self.action in WRITE_ACTIONS:
            return [IsAdmin()]
        return super().get_permissions()

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

    def destroy(self, request, *args, **kwargs):
        """Delete the instructor row together with their login account.

        The profile is a OneToOne CASCADE of the user, so removing the account
        removes the instructor too. Accounts still referenced by PROTECT
        relations (attendance sessions, course offerings, append-only audit
        logs) cannot be removed without losing history — those are deactivated
        instead, matching ``UserViewSet.destroy``.
        """
        instructor = self.get_object()
        user = instructor.user
        if getattr(request.user, "pk", None) == user.pk:
            return Response(
                {"success": False, "message": "ไม่สามารถลบบัญชีของตนเองได้", "code": "FORBIDDEN"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user_pk = user.pk
        try:
            with transaction.atomic():
                user.delete()
        except ProtectedError:
            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])
            instructor.status = "inactive"
            instructor.save(update_fields=["status", "updated_at"])
            log_audit(request.user, "user_deactivate", "user", user_pk, request=request)
            return success_response(
                {"id": str(user_pk), "is_active": False, "instructor_status": "inactive"},
                "บัญชีอาจารย์ถูกอ้างอิงโดยประวัติการใช้งาน — ระงับบัญชีแทนการลบ",
            )
        log_audit(request.user, "user_delete", "user", user_pk, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)
