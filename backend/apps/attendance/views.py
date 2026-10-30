"""Attendance endpoints (spec §10, §13.1).

Permissions:
- Instructors operate only on sessions of offerings they teach (primary or co-instructor).
- Admins have full scope; students only check in and read their own records.
"""
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response

from apps.accounts.models import StudentProfile
from apps.audit.models import log_audit
from apps.audit.throttles import CheckInThrottle
from apps.attendance import services
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.attendance.serializers import (
    AttendanceRecordSerializer,
    AttendanceRecordUpdateSerializer,
    AttendanceSessionCreateSerializer,
    AttendanceSessionSerializer,
    CheckInResultSerializer,
    CheckInSerializer,
    QRTokenSerializer,
    SessionRosterSerializer,
)
from common.permissions import IsAdmin, IsAdminOrInstructor, IsInstructor, RoleRequired
from common.responses import error_response, success_response


class SessionScopeMixin:
    """Restricts querysets to instructor-owned offerings where applicable."""

    def scoped(self, queryset, action_scope="view"):
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                # Fail closed: a profile-less instructor account sees nothing
                # (previously fell through to the unscoped queryset and
                # exposed every session).
                return queryset.none()
            # อาจารย์หลักหรืออาจารย์ผู้รับผิดชอบร่วม ต่างก็เห็นคาบของรายวิชานี้
            return queryset.filter(
                Q(course_offering__instructor=profile) | Q(course_offering__instructors=profile)
            ).distinct()
        return queryset

    def can_manage(self, session: AttendanceSession) -> bool:
        user = self.request.user
        if user.role == "admin":
            return True
        if user.role == "instructor" and getattr(user, "instructor_profile", None):
            return session.course_offering.has_instructor(user.instructor_profile)
        return False


class AttendanceSessionViewSet(SessionScopeMixin, viewsets.ModelViewSet):
    """Create/read sessions; lifecycle managed via /open /pause /close /cancel."""

    serializer_class = AttendanceSessionSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = {
        "course_offering": ["exact"],
        "status": ["exact"],
        "session_date": ["exact", "gte", "lte"],
    }
    ordering_fields = ["session_date", "check_in_start", "created_at"]
    ordering = ["-session_date", "-created_at"]
    search_fields = ["course_offering__course__course_code"]

    def get_serializer_class(self):
        if self.action == "create":
            return AttendanceSessionCreateSerializer
        return AttendanceSessionSerializer

    def get_queryset(self):
        return self.scoped(
            AttendanceSession.objects.select_related(
                "course_offering", "course_offering__course",
                "course_offering__academic_term", "instructor", "class_schedule",
            )
        )

    def create(self, request, *args, **kwargs):
        """Only the offering's instructor (or admin) may create a session."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        offering = serializer.validated_data["course_offering"]
        user = request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                return error_response(
                    "บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน",
                    "NO_INSTRUCTOR_PROFILE", 400
                )
            if offering.instructor_id != profile.id and not offering.instructors.filter(
                pk=profile.pk
            ).exists():
                return error_response(
                    "คุณไม่ได้เป็นอาจารย์ผู้รับผิดชอบรายวิชานี้", "PERMISSION_DENIED", 403
                )
        existing = AttendanceSession.objects.filter(
            course_offering=offering, session_date=serializer.validated_data["session_date"]
        ).first()
        if existing:
            return error_response(
                "มีคาบเรียนของวันนี้อยู่แล้ว กรุณาใช้คาบที่มีอยู่ เพื่อป้องกันการเปิดซ้ำโดยไม่ตั้งใจ",
                "SESSION_ALREADY_EXISTS", status.HTTP_409_CONFLICT,
            )
        session = serializer.save()
        log_audit(request.user, "session_create", "attendance_session", session.pk, request=request)
        return success_response(
            self.get_serializer(session).data, "สร้างคาบเรียนสำเร็จ",
            status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="open")
    def open_action(self, request, pk=None):
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์จัดการคาบนี้", "PERMISSION_DENIED", 403)
        try:
            session = services.open_session(session, request.user)
        except Exception as exc:
            from rest_framework.exceptions import ValidationError as DRFValidationError

            if isinstance(exc, DRFValidationError):
                return error_response(str(exc.detail if hasattr(exc, "detail") else exc), "SESSION_STATE_INVALID", 400)
            raise
        data = self.get_serializer(session).data
        qr_payload = QRTokenSerializer(session.current_token).data
        qr_payload["qr"] = session.current_token.raw  # returned once; never stored
        data["qr"] = qr_payload
        return success_response(data, "เปิดเช็คชื่อสำเร็จ")

    @action(detail=True, methods=["post"], url_path="pause")
    def pause_action(self, request, pk=None):
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์จัดการคาบนี้", "PERMISSION_DENIED", 403)
        session = services.pause_session(session)
        return success_response(self.get_serializer(session).data, "หยุดเช็คชื่อชั่วคราวแล้ว")

    @action(detail=True, methods=["post"], url_path="close")
    def close_action(self, request, pk=None):
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์จัดการคาบนี้", "PERMISSION_DENIED", 403)
        session = services.close_session(session, request.user)
        return success_response(self.get_serializer(session).data, "ปิดคาบเรียนสำเร็จ — นักศึกษาที่ไม่ได้เช็คชื่อถูกบันทึกขาดเรียน")

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel_action(self, request, pk=None):
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์จัดการคาบนี้", "PERMISSION_DENIED", 403)
        session = services.cancel_session(session, request.user)
        return success_response(self.get_serializer(session).data, "ยกเลิกคาบเรียนสำเร็จ")

    @action(detail=True, methods=["post"], url_path="qr-token")
    def qr_token(self, request, pk=None):
        """Issue/rotate the on-screen QR token for this live session."""
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์จัดการคาบนี้", "PERMISSION_DENIED", 403)
        token = services.issue_token(session, request.user)
        session.current_token = token
        import hashlib  # local use only; not logged

        data = QRTokenSerializer(token).data
        data["qr"] = token.raw  # returned once to display; never stored nor logged
        return success_response(data, "ออก QR Code สำเร็จ")

    @action(detail=True, methods=["get"], url_path="roster")
    def roster(self, request, pk=None):
        session = self.get_object()
        if not self.can_manage(session):
            return error_response("คุณไม่มีสิทธิ์ดูคาบนี้", "PERMISSION_DENIED", 403)
        records = {r.student_id: r for r in session.records.all()}
        rows = []
        enrolled = session.course_offering.enrollments.filter(
            enrollment_status="enrolled"
        ).select_related("student")
        for e in enrolled:
            s = e.student
            rec = records.get(s.id)
            rows.append({
                "id": str(s.id),
                "student_code": s.student_code,
                "student_name": f"{s.first_name} {s.last_name}",
                "checked_in_status": rec.status if rec else None,
                "checked_in_at": rec.checked_in_at if rec else None,
            })
        rows.sort(key=lambda r: r["student_code"])
        return success_response(rows, "โหลดรายชื่อคาบเรียนสำเร็จ")


class AttendanceRecordViewSet(viewsets.ModelViewSet):
    """Attendance records list (admin/instructor full scope; students own only)."""

    serializer_class = AttendanceRecordSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
    http_method_names = ["get", "patch", "head", "options"]
    filter_backends = [DjangoFilterBackend, OrderingFilter, SearchFilter]
    filterset_fields = {
        "attendance_session": ["exact"],
        "student": ["exact"],
        "status": ["exact"],
        "attendance_session__course_offering": ["exact"],
        "checked_in_at": ["gte", "lte"],
    }
    search_fields = ["student__student_code", "student__first_name", "student__last_name"]
    ordering_fields = ["checked_in_at", "status"]
    ordering = ["-checked_in_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return AttendanceRecord.objects.none()
        from apps.attendance.models import AttendanceRecord as R

        qs = R.objects.select_related(
            "student", "attendance_session", "attendance_session__course_offering",
            "attendance_session__course_offering__course", "edited_by",
        )
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                return qs.none()
            return qs.filter(
                Q(attendance_session__course_offering__instructor=profile)
                | Q(attendance_session__course_offering__instructors=profile)
            ).distinct()
        return qs

    def get_serializer_class(self):
        if self.action == "partial_update" or self.action == "update":
            return AttendanceRecordUpdateSerializer
        return AttendanceRecordSerializer

    def partial_update(self, request, pk=None):
        record = self.get_object()
        serializer = self.get_serializer(record, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        record = serializer.save(edited_by=request.user)
        log_audit(
            request.user, "attendance_record_edit", "attendance_record", record.pk,
            metadata={"status": record.status, "reason": record.edit_reason[:120]},
            request=request,
        )
        return success_response(
            AttendanceRecordSerializer(record).data, "แก้ไขสถานะการเข้าเรียนสำเร็จ"
        )


class CheckInView(APIView):
    """Student QR check-in. Only the scanned token is accepted from the body."""

    permission_classes = [RoleRequired]
    allowed_roles = {"student"}
    throttle_classes = [CheckInThrottle]

    @extend_schema(
        request=CheckInSerializer,
        responses=CheckInResultSerializer,
        summary="เช็คชื่อผ่าน QR Token",
    )
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            record = services.check_in(request.user, serializer.validated_data["token"])
        except Exception:
            raise
        from apps.attendance.serializers import CheckInResultSerializer

        session = record.attendance_session
        offering = session.course_offering
        result = {
            "attendance_session": str(session.pk),
            "course_code": offering.course.course_code,
            "course_name": offering.course.course_name,
            "session_date": session.session_date,
            "status": record.status,
            "checked_in_at": record.checked_in_at,
        }
        if record.status == "late":
            message = "เช็คชื่อมาสายแล้ว — บันทึกสถานะมาสาย"
        else:
            message = "เช็คชื่อสำเร็จ"
        return success_response(CheckInResultSerializer(result).data, message)


class StudentMyHistoryView(APIView):
    """My attendance history — ownership enforced: always scoped to
    request.user's own student profile."""

    permission_classes = [RoleRequired]
    allowed_roles = {"student"}
    filter_backends = [DjangoFilterBackend, OrderingFilter]

    @extend_schema(
        responses=AttendanceRecordSerializer(many=True),
        summary="ประวัติการเช็คชื่อของตนเอง",
    )
    def get(self, request):
        profile = getattr(request.user, "student_profile", None)
        if profile is None:
            return success_response([], "โหลดประวัติการเช็คชื่อสำเร็จ")
        records = AttendanceRecord.objects.filter(student=profile).select_related(
            "attendance_session", "attendance_session__course_offering", "attendance_session__course_offering__course",
            "edited_by",
        ).order_by("-checked_in_at")
        data = AttendanceRecordSerializer(records, many=True).data
        return success_response(data, "โหลดประวัติการเช็คชื่อสำเร็จ")
