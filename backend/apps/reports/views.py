"""Attendance reports with server-side filtering and CSV export (spec §11)."""
from django.db.models import Count, Q
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import viewsets, serializers
from rest_framework.views import APIView
from rest_framework import status

from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.audit.models import log_audit
from common.csvutils import rows_to_csv_bytes
from common.permissions import IsAdminOrInstructor, RoleRequired
from common.responses import success_response


class AttendanceReportDataSerializer(serializers.Serializer):
    data = serializers.JSONField(help_text="รายงานอัตราการเข้าเรียนตามสูตร spec §11.1")


class CsvExportSerializer(serializers.Serializer):
    success = serializers.BooleanField()


def _term_scope_filter(params):
    """Build record filters from query params (server-side filtering)."""
    from django.db.models import Q as _Q

    filters = _Q()
    offering = params.get("course_offering")
    if offering:
        filters &= _Q(attendance_session__course_offering_id=offering)
    term = params.get("term")
    if term:
        filters &= _Q(attendance_session__course_offering__academic_term_id=term)
    program = params.get("program")
    if program:
        filters &= _Q(student__program_id=program)
    group = params.get("class_group")
    if group:
        filters &= _Q(student__class_group_id=group)
    student = params.get("student")
    if student:
        filters &= _Q(student_id=student)
    date_from = params.get("date_from")
    if date_from:
        filters &= _Q(attendance_session__session_date__gte=date_from)
    date_to = params.get("date_to")
    if date_to:
        filters &= _Q(attendance_session__session_date__lte=date_to)
    return filters


class AttendanceReportView(APIView):
    """Per-student report — only CLOSED sessions count toward rates.

    Attendance-rate formula (spec §11.1):
      rate = (present + late) / (present + late + absent + excused) * 100
      — Open/Cancelled/Scheduled sessions are excluded entirely.
    """

    permission_classes = [IsAdminOrInstructor]

    @extend_schema(responses=AttendanceReportDataSerializer, summary="รายงานอัตราการเข้าเรียน (นับเฉพาะคาบปิดแล้ว)")
    def get(self, request):
        user = request.user
        qs = AttendanceSession.objects.filter(status="closed")
        if user.role == "instructor" and getattr(user, "instructor_profile", None):
            qs = qs.filter(course_offering__instructor=user.instructor_profile)
        from django.db.models import Q as _Q

        # Sessions included per the formula — none of the open ones
        offering = request.query_params.get("course_offering")
        if offering:
            qs = qs.filter(course_offering_id=offering)
        term = request.query_params.get("term")
        if term:
            qs = qs.filter(course_offering__academic_term_id=term)
        program = request.query_params.get("program")
        if program:
            qs = qs.filter(course_offering__class_group__program_id=program)
        group = request.query_params.get("class_group")
        if group:
            qs = qs.filter(course_offering__class_group_id=group)
        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(session_date__gte=date_from)
        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(session_date__lte=date_to)
        student = request.query_params.get("student")
        if student:
            qs = qs.filter(course_offering__enrollments__student_id=student)

        records = AttendanceRecord.objects.filter(
            attendance_session_id__in=qs.values("id"),
        ).values(
            "student_id",
            "student__student_code",
            "student__first_name",
            "student__last_name",
        ).annotate(
            present=Count("id", filter=Q(status="present")),
            late=Count("id", filter=Q(status="late")),
            absent=Count("id", filter=Q(status="absent")),
            excused=Count("id", filter=Q(status="excused")),
        ).order_by("student__student_code")

        # Denominator: total eligible sessions found across the filter — same
        # count for every student in the same cohort (they are all enrolled).
        total_eligible = qs.count()
        rows = []
        for r in records:
            attended = r["present"] + r["late"]
            denominator = r["present"] + r["late"] + r["absent"] + r["excused"]
            rate = round(attended / denominator * 100, 2) if denominator else 0.0
            rows.append({
                "student_id": str(r["student_id"]),
                "student_code": r["student__student_code"],
                "student_name": f"{r['student__first_name']} {r['student__last_name']}",
                "present": r["present"],
                "late": r["late"],
                "absent": r["absent"],
                "excused": r["excused"],
                "eligible_sessions": denominator or 0,
                "attendance_rate": rate,
            })
        return success_response(
            {
                "rows": rows,
                "total_closed_sessions": total_eligible,
                "formula": "(present + late) / (present + late + absent + excused) * 100",
                "note": "นับเฉพาะคาบปิดแล้ว; คาบที่เปิดอยู่/ยกเลิกไม่นับ",
            },
            "โหลดรายงานการเข้าเรียนสำเร็จ",
        )


class AttendanceReportExportView(APIView):
    """CSV export — sanitized against formula injection (spec §16)."""

    permission_classes = [IsAdminOrInstructor]

    @extend_schema(
        responses={(200, "text/csv"): None},
        summary="ส่งออกรายงาน CSV (ป้องกัน formula injection)",
    )
    def get(self, request):
        report = AttendanceReportView()
        report.request = request
        # Reuse the same computation
        data = report.get(request).data
        rows = data["data"]["rows"]
        csv_bytes = rows_to_csv_bytes(
            ["student_code", "name", "present", "late", "absent", "excused", "eligible_sessions", "attendance_rate_%"],
            [
                [
                    r["student_code"], r["student_name"], r["present"], r["late"],
                    r["absent"], r["excused"], r["eligible_sessions"], r["attendance_rate"],
                ]
                for r in rows
            ],
        )
        log_audit(request.user, "report_export", "attendance_report", request=request)
        response = HttpResponse(csv_bytes, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            'attachment; filename="attendance_report.csv"'
        )
        return response
