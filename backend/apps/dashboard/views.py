"""Dashboard aggregates — real data from the database (no mock values)."""
from datetime import timedelta

from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.serializers import JSONField, Serializer
from rest_framework.views import APIView

from apps.accounts.models import InstructorProfile, StudentProfile, User
from apps.academics.models import AcademicTerm, Program
from apps.schedules.models import ClassSchedule
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import Course, CourseOffering
from common.permissions import IsAdmin, IsInstructor, RoleRequired
from common.responses import success_response


class DashboardDataSerializer(Serializer):
    data = JSONField(help_text="ตัวเลขภาพรวมจากฐานข้อมูลจริง (โครงสร้างตาม spec §7.1)")


def admin_summary():
    """Internal helper returning the numbers — shared by view and healthcheck."""
    today = timezone.localdate()
    sessions_all = AttendanceSession.objects.all()
    return {
        "users_total": User.objects.count(),
        "users_active": User.objects.filter(is_active=True).count(),
        "students_total": StudentProfile.objects.count(),
        "instructors_total": InstructorProfile.objects.count(),
        "programs_total": Program.objects.count(),
        "courses_total": Course.objects.count(),
        "courses_active": Course.objects.filter(is_active=True).count(),
        "offerings_total": CourseOffering.objects.count(),
        "sessions_total": sessions_all.count(),
        "sessions_open": sessions_all.filter(status="open").count(),
        "sessions_today": sessions_all.filter(session_date=today).count(),
        "records_today": AttendanceRecord.objects.filter(
            checked_in_at__date=today
        ).count(),
        "records_this_week": AttendanceRecord.objects.filter(
            checked_in_at__gte=timezone.now() - timedelta(days=7)
        ).count(),
    }


class AdminDashboardView(APIView):
    """Admin dashboard numbers (spec §7.1). Real DB queries only."""

    permission_classes = [IsAdmin]

    @extend_schema(responses=DashboardDataSerializer, summary="แดชบอร์ดผู้ดูแลระบบ")
    def get(self, request):
        # Last 14 days daily check-in count (daily trend used by charts)
        now = timezone.now()
        start = (now - timedelta(days=13)).date()
        daily = (
            AttendanceRecord.objects.filter(
                attendance_session__status="closed",
                checked_in_at__date__gte=start,
            )
            .exclude(status="absent")
            .values("checked_in_at__date")
            .annotate(present=Count("id"))
            .order_by("checked_in_at__date")
        )
        trend = [
            {"date": row["checked_in_at__date"].isoformat(), "count": row["present"]}
            for row in daily
        ]
        breakdown = dict(
            AttendanceRecord.objects.values_list("status")
            .annotate(c=Count("id"))
        )
        # Program enrollment mix — real counts from course data.
        program_mix = [
            {"program": row["program__program_name"], "students": row["c"]}
            for row in StudentProfile.objects.values("program__program_name")
            .annotate(c=Count("id"))
            .order_by("-c")
        ]
        # High-absence courses — bottom 5 by rate among closed sessions.
        high_absence = _high_absence_courses(request.user)
        data = admin_summary()
        data.update(
            {
                "daily_trend": trend,
                "status_breakdown": breakdown,
                "program_students": program_mix,
                "high_absence_courses": high_absence,
            }
        )
        return success_response(data, "โหลดภาพรวมระบบสำเร็จ")


def _high_absence_courses(user, limit: int = 5):
    from django.db.models import F, ExpressionWrapper, FloatField

    per_course = (
        AttendanceRecord.objects.filter(attendance_session__status="closed")
        .values(
            "attendance_session__course_offering__course__course_code",
            "attendance_session__course_offering__course__course_name",
        )
        .annotate(
            total=Count("id"),
            absent_count=Count("id", filter=Q(status="absent")),
        )
        .filter(total__gt=0)
        .annotate(
            absence_rate=ExpressionWrapper(
                F("absent_count") * 100.0 / F("total"), output_field=FloatField()
            )
        )
        .order_by("-absence_rate")[:limit]
    )
    return [
        {
            "course_code": row["attendance_session__course_offering__course__course_code"],
            "course_name": row["attendance_session__course_offering__course__course_name"],
            "total_records": row["total"],
            "absent_count": row["absent_count"],
            "absence_rate": round(row["absence_rate"], 2),
        }
        for row in per_course
    ]


class InstructorDashboardView(APIView):
    """Instructor dashboard — only their own assignments."""

    permission_classes = [IsInstructor]

    @extend_schema(responses=DashboardDataSerializer, summary="แดชบอร์ดอาจารย์ (เฉพาะรายวิชาของตนเอง)")
    def get(self, request):
        profile = getattr(request.user, "instructor_profile", None)
        if profile is None:
            return success_response(
                {
                    "offerings": [],
                    "sessions_today": 0,
                    "open_session_id": None,
                    "total_records": 0,
                    "total_absent": 0,
                    "status_breakdown": {},
                },
                "โหลดแดชบอร์ดอาจารย์สำเร็จ",
            )
        offerings = CourseOffering.objects.filter(instructor=profile).select_related("course", "academic_term")
        sessions_today = AttendanceSession.objects.filter(
            course_offering__instructor=profile,
            session_date=timezone.localdate(),
        )
        open_session = sessions_today.filter(Q(status="open") | Q(status="paused")).first()
        total_records = AttendanceRecord.objects.filter(
            attendance_session__course_offering__instructor=profile,
        ).count()
        total_absent = AttendanceRecord.objects.filter(
            attendance_session__course_offering__instructor=profile,
            status="absent",
        ).count()
        data = {
            "offerings": [
                {
                    "id": str(o.pk),
                    "course_code": o.course.course_code,
                    "course_name": o.course.course_name,
                    "term": f"{o.academic_term.academic_year}/{o.academic_term.semester}",
                    "enrolled": o.enrollments.filter(enrollment_status="enrolled").count(),
                    "status": o.status,
                }
                for o in offerings
            ],
            "sessions_today": sessions_today.count(),
            "open_session_id": str(open_session.pk) if open_session else None,
            "total_records": total_records,
            "total_absent": total_absent,
            "status_breakdown": dict(
                AttendanceRecord.objects.filter(
                    attendance_session__course_offering__instructor=profile,
                ).values_list("status").annotate(c=Count("id"))
            ),
        }
        return success_response(data, "โหลดแดชบอร์ดอาจารย์สำเร็จ")


class StudentDashboardView(APIView):
    """Student dashboard — own data only (IDOR-safe by construction)."""

    permission_classes = [RoleRequired]
    allowed_roles = {"student"}

    @extend_schema(responses=DashboardDataSerializer, summary="แดชบอร์ดนักศึกษา (เฉพาะข้อมูลของตนเอง)")
    def get(self, request):
        profile = getattr(request.user, "student_profile", None)
        if profile is None:
            return success_response(
                {
                    "profile": None,
                    "courses": [],
                    "schedules": [],
                    "statistics": {"present": 0, "late": 0, "absent": 0, "excused": 0},
                    "recent_records": [],
                    "current_term": None,
                },
                "โหลดแดชบอร์ดนักศึกษาสำเร็จ",
            )
        my_records = AttendanceRecord.objects.filter(student=profile)
        enrolled_offerings = CourseOffering.objects.filter(
            enrollments__student=profile,
            enrollments__enrollment_status="enrolled",
        ).select_related("course", "academic_term")
        active_offerings = enrolled_offerings.exclude(status="cancelled")
        schedules = ClassSchedule.objects.filter(
            course_offering__in=active_offerings,
            status="active",
        ).select_related("course_offering", "course_offering__course").order_by("weekday", "start_time")
        data = {
            "profile": {
                "student_code": profile.student_code,
                "first_name": profile.first_name,
                "last_name": profile.last_name,
                "email": request.user.email,
                "username": request.user.username,
                "program_name": profile.program.program_name if profile.program_id else None,
                "class_group_name": profile.class_group.group_name if profile.class_group_id else None,
                "academic_year_level": profile.academic_year_level,
                "status": profile.status,
                "status_display": profile.get_status_display(),
            },
            "courses": [
                {
                    "id": str(o.pk),
                    "course_code": o.course.course_code,
                    "course_name": o.course.course_name,
                    "term": f"{o.academic_term.academic_year}/{o.academic_term.semester}",
                }
                for o in enrolled_offerings
            ],
            "schedules": [
                {
                    "id": str(s.pk),
                    "course_code": s.course_offering.course.course_code,
                    "course_name": s.course_offering.course.course_name,
                    "weekday": s.weekday,
                    "weekday_display": s.get_weekday_display(),
                    "start_time": str(s.start_time),
                    "end_time": str(s.end_time),
                    "classroom": s.classroom,
                    "status": s.status,
                }
                for s in schedules
            ],
            "statistics": {
                "present": my_records.filter(status="present").count(),
                "late": my_records.filter(status="late").count(),
                "absent": my_records.filter(status="absent").count(),
                "excused": my_records.filter(status="excused").count(),
            },
            "recent_records": [
                {
                    "course_code": r.attendance_session.course_offering.course.course_code,
                    "session_date": r.attendance_session.session_date,
                    "status": r.status,
                    "checked_in_at": r.checked_in_at,
                }
                for r in my_records.select_related(
                    "attendance_session__course_offering__course"
                ).order_by("-checked_in_at")[:10]
            ],
        }
        terms = AcademicTerm.objects.filter(is_current=True).first()
        data["current_term"] = (
            f"{terms.academic_year}/{terms.semester}" if terms else None
        )
        return success_response(data, "โหลดแดชบอร์ดนักศึกษาสำเร็จ")
