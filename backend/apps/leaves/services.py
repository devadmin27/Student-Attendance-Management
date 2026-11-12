"""Leave request business logic and attendance read-only projection.

Nothing in this module writes AttendanceRecord/AttendanceSession. The roster
only asks for a leave-status map and displays it alongside (never instead of)
the attendance status (spec §5.2).
"""
from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import StudentProfile
from apps.attendance.models import AttendanceSession
from apps.courses.models import Enrollment
from apps.leaves.models import (
    LeaveAttachment,
    LeaveCourse,
    LeaveCourseReview,
    LeaveRequest,
)


# ---------------------------------------------------------------------------
# Submission policy (Phase 4)
# ---------------------------------------------------------------------------
def leave_policy() -> dict:
    """Policy payload for the SPA — thresholds live in Django settings only."""
    return {
        "personal_advance_days": settings.LEAVE_PERSONAL_ADVANCE_DAYS,
        "sick_normal_grace_days": settings.LEAVE_SICK_NORMAL_GRACE_DAYS,
        "sick_late_grace_days": settings.LEAVE_SICK_LATE_GRACE_DAYS,
        "medical_certificate_min_days": settings.LEAVE_MEDICAL_CERTIFICATE_MIN_DAYS,
        "max_attachment_bytes": settings.LEAVE_ATTACHMENT_MAX_BYTES,
        "max_attachment_count": settings.LEAVE_ATTACHMENT_MAX_COUNT,
        "allowed_attachment_extensions": settings.LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS,
        "allowed_attachment_content_types": (
            settings.LEAVE_ATTACHMENT_ALLOWED_CONTENT_TYPES
        ),
        "server_date": timezone.localdate().isoformat(),
    }


def submission_deadlines(
    leave_type: str,
    start_date: date,
    end_date: date,
) -> tuple[date | None, date | None]:
    """Return (normal deadline, late-grace deadline) for a request.

    - personal: must be filed on or before start_date − advance_days.
    - sick: normal deadline is end_date + normal grace (day after the leave);
      the late-grace deadline is end_date + late grace.
    - other: no timing restriction.
    """
    if leave_type == "personal":
        return (
            start_date - timedelta(days=settings.LEAVE_PERSONAL_ADVANCE_DAYS),
            None,
        )
    if leave_type == "sick":
        return (
            end_date + timedelta(days=settings.LEAVE_SICK_NORMAL_GRACE_DAYS),
            end_date + timedelta(days=settings.LEAVE_SICK_LATE_GRACE_DAYS),
        )
    return None, None


def requires_medical_certificate(leave_request: LeaveRequest) -> bool:
    return (
        leave_request.leave_type == "sick"
        and leave_request.total_days
        >= settings.LEAVE_MEDICAL_CERTIFICATE_MIN_DAYS
    )


def validate_submission_timing(
    leave_request: LeaveRequest,
    today: date | None = None,
) -> None:
    """Enforce the college's advance/retroactive submission window.

    Personal leave must be submitted at least N days before it starts. Sick
    leave may be submitted up to the day after it ends; a short grace period
    after that is still accepted when a late-submission reason is supplied.
    """
    if leave_request.leave_type not in ("personal", "sick"):
        return
    today = today or timezone.localdate()
    normal_deadline, grace_deadline = submission_deadlines(
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
    )
    if leave_request.leave_type == "personal":
        if normal_deadline is not None and today > normal_deadline:
            raise ValidationError(
                {"start_date": [
                    "ลากิจส่วนตัวต้องส่งล่วงหน้าอย่างน้อย "
                    f"{settings.LEAVE_PERSONAL_ADVANCE_DAYS} วัน "
                    f"(ภายใน {normal_deadline.strftime('%d/%m/%Y')})"
                ]}
            )
        return

    if grace_deadline is not None and today > grace_deadline:
        raise ValidationError(
            {"end_date": [
                "เลยกำหนดส่งใบลาป่วยแล้ว — ส่งได้ไม่เกิน "
                f"{settings.LEAVE_SICK_LATE_GRACE_DAYS} วันหลังวันสิ้นสุดการลา "
                f"(ภายใน {grace_deadline.strftime('%d/%m/%Y')})"
            ]}
        )
    if (
        normal_deadline is not None
        and today > normal_deadline
        and not (leave_request.late_submission_reason or "").strip()
    ):
        raise ValidationError(
            {"late_submission_reason": [
                "ส่งใบลาป่วยเกินกำหนดปกติแล้ว กรุณาระบุเหตุผลการส่งย้อนหลัง"
            ]}
        )


def validate_medical_certificate(leave_request: LeaveRequest) -> None:
    if not requires_medical_certificate(leave_request):
        return
    if not leave_request.attachments.filter(
        attachment_type="medical_certificate"
    ).exists():
        raise ValidationError(
            {"attachments": [
                "ลาป่วยตั้งแต่ "
                f"{settings.LEAVE_MEDICAL_CERTIFICATE_MIN_DAYS} วันขึ้นไป "
                "ต้องแนบใบรับรองแพทย์ก่อนส่งคำร้อง"
            ]}
        )


# ---------------------------------------------------------------------------
# Range helpers
# ---------------------------------------------------------------------------
def validate_leave_range(
    start_date: date,
    end_date: date,
    start_time: time | None,
    end_time: time | None,
) -> None:
    errors: dict[str, list[str]] = {}
    if start_date and end_date and end_date < start_date:
        errors["end_date"] = ["วันที่สิ้นสุดการลาต้องไม่ก่อนวันที่เริ่มลา"]
    if bool(start_time) != bool(end_time):
        errors["end_time"] = ["ต้องระบุเวลาเริ่มและเวลาสิ้นสุดพร้อมกัน หรือไม่ระบุทั้งคู่"]
    elif (
        start_time and end_time and start_date == end_date and end_time <= start_time
    ):
        errors["end_time"] = ["เวลาสิ้นสุดการลาต้องอยู่หลังเวลาเริ่มลา"]
    if errors:
        raise ValidationError(errors)


def iter_dates(start_date: date, end_date: date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _times_overlap(
    leave_start: time | None, leave_end: time | None,
    window_start: time, window_end: time,
) -> bool:
    """A request without times covers the whole day."""
    if leave_start is None or leave_end is None:
        return True
    return leave_start < window_end and leave_end > window_start


def session_time_window(session: AttendanceSession) -> tuple[time, time]:
    """Use the linked schedule's clock times, else the check-in window."""
    schedule = session.class_schedule
    if schedule is not None:
        return schedule.start_time, schedule.end_time
    start = timezone.localtime(session.check_in_start).time()
    end = timezone.localtime(session.check_in_end).time()
    return start, end


def _schedule_occurrences(offering, start_date, end_date, start_time, end_time):
    """Return the dates on which one offering's weekly schedule overlaps."""
    occurrences: list[dict] = []
    schedules = [
        s for s in offering.schedules.all()
        if s.status != "cancelled"
    ]
    if not schedules:
        return occurrences
    for day in iter_dates(start_date, end_date):
        weekday = day.weekday()  # Monday=0 matches ClassSchedule choices
        for schedule in schedules:
            if schedule.weekday != weekday:
                continue
            if not _times_overlap(
                start_time, end_time, schedule.start_time, schedule.end_time
            ):
                continue
            occurrences.append(
                {
                    "date": day.isoformat(),
                    "weekday": schedule.weekday,
                    "weekday_display": schedule.get_weekday_display(),
                    "start_time": schedule.start_time.strftime("%H:%M"),
                    "end_time": schedule.end_time.strftime("%H:%M"),
                    "classroom": schedule.classroom,
                }
            )
    occurrences.sort(key=lambda item: (item["date"], item["start_time"]))
    return occurrences


# ---------------------------------------------------------------------------
# Available courses
# ---------------------------------------------------------------------------
def available_courses(
    student: StudentProfile,
    start_date: date,
    end_date: date,
    start_time: time | None = None,
    end_time: time | None = None,
) -> list[dict]:
    """Student's enrolled offerings annotated with schedule coverage.

    All enrolled, non-cancelled offerings are returned (the student decides
    which ones are relevant). `has_class_in_period` / `affected_dates` are
    suggestions derived from ClassSchedule — never a hard block.
    """
    validate_leave_range(start_date, end_date, start_time, end_time)
    enrollments = (
        Enrollment.objects.filter(student=student, enrollment_status="enrolled")
        .exclude(course_offering__status="cancelled")
        .select_related(
            "course_offering",
            "course_offering__course",
            "course_offering__academic_term",
            "course_offering__class_group",
        )
        .prefetch_related("course_offering__schedules")
    )
    results = []
    for enrollment in enrollments:
        offering = enrollment.course_offering
        occurrences = _schedule_occurrences(
            offering, start_date, end_date, start_time, end_time
        )
        schedules = [
            {
                "weekday": schedule.weekday,
                "weekday_display": schedule.get_weekday_display(),
                "start_time": schedule.start_time.strftime("%H:%M"),
                "end_time": schedule.end_time.strftime("%H:%M"),
                "classroom": schedule.classroom,
            }
            for schedule in offering.schedules.all()
            if schedule.status != "cancelled"
        ]
        term = offering.academic_term
        results.append(
            {
                "id": str(offering.id),
                "course_code": offering.course.course_code,
                "course_name": offering.course.course_name,
                "term_label": f"{term.academic_year}/{term.semester}",
                "class_group_name": (
                    offering.class_group.group_name if offering.class_group else None
                ),
                "schedules": schedules,
                "has_class_in_period": bool(occurrences),
                "affected_count": len(occurrences),
                "affected_dates": [item["date"] for item in occurrences],
                "affected_classes": occurrences,
            }
        )
    results.sort(key=lambda item: item["course_code"])
    return results


# ---------------------------------------------------------------------------
# Draft mutation
# ---------------------------------------------------------------------------
def set_courses(leave_request: LeaveRequest, offering_ids) -> None:
    """Replace the request's courses with the selected enrolled offerings."""
    student = leave_request.student
    ids = list(dict.fromkeys(str(value) for value in offering_ids if value))
    if ids:
        enrolled = {
            str(row.course_offering_id): row
            for row in Enrollment.objects.filter(
                student=student,
                enrollment_status="enrolled",
                course_offering_id__in=ids,
            ).exclude(course_offering__status="cancelled").select_related("course_offering")
        }
        missing = [value for value in ids if value not in enrolled]
        if missing:
            raise ValidationError(
                {"course_offering_ids": [
                    "บางรายวิชาไม่ได้อยู่ในรายการลงทะเบียนที่ใช้งานอยู่"
                ]}
            )
    else:
        enrolled = {}

    leave_request.courses.exclude(
        course_offering_id__in=ids
    ).delete()
    for value in ids:
        LeaveCourse.objects.update_or_create(
            leave_request=leave_request,
            course_offering=enrolled[value].course_offering,
            defaults={
                "affected_start_date": leave_request.start_date,
                "affected_end_date": leave_request.end_date,
                "affected_start_time": leave_request.start_time,
                "affected_end_time": leave_request.end_time,
            },
        )


def refresh_affected_windows(leave_request: LeaveRequest) -> None:
    leave_request.courses.update(
        affected_start_date=leave_request.start_date,
        affected_end_date=leave_request.end_date,
        affected_start_time=leave_request.start_time,
        affected_end_time=leave_request.end_time,
    )


def submit_leave_request(leave_request: LeaveRequest) -> LeaveRequest:
    if leave_request.status != "draft":
        raise ValidationError({"status": ["ส่งได้เฉพาะคำร้องที่เป็นแบบร่าง"]})
    if not leave_request.courses.exists():
        raise ValidationError({"course_offering_ids": ["กรุณาเลือกอย่างน้อย 1 รายวิชา"]})
    if not (leave_request.reason or "").strip():
        raise ValidationError({"reason": ["กรุณาระบุเหตุผลการลา"]})
    validate_leave_range(
        leave_request.start_date,
        leave_request.end_date,
        leave_request.start_time,
        leave_request.end_time,
    )
    validate_submission_timing(leave_request)
    validate_medical_certificate(leave_request)
    leave_request.status = "submitted"
    leave_request.submitted_at = timezone.now()
    leave_request.save(update_fields=["status", "submitted_at", "updated_at"])
    return leave_request


def cancel_leave_request(leave_request: LeaveRequest) -> LeaveRequest:
    if not leave_request.is_cancellable:
        raise ValidationError({"status": ["คำร้องนี้ไม่สามารถยกเลิกได้"]})
    leave_request.status = "cancelled"
    leave_request.cancelled_at = timezone.now()
    leave_request.save(update_fields=["status", "cancelled_at", "updated_at"])
    return leave_request


# ---------------------------------------------------------------------------
# Attachments (private files)
# ---------------------------------------------------------------------------
def create_leave_attachment(
    leave_request: LeaveRequest,
    uploaded_file,
    attachment_type: str,
    uploaded_by,
) -> LeaveAttachment:
    """Store one attachment for a draft request.

    The serializer validates extension/size; this service adds the business
    rules (draft-only, attachment count cap) and records metadata.
    """
    if leave_request.status != "draft":
        raise ValidationError(
            {"status": ["แนบไฟล์ได้เฉพาะคำร้องที่เป็นแบบร่าง"]}
        )
    if (
        leave_request.attachments.count()
        >= settings.LEAVE_ATTACHMENT_MAX_COUNT
    ):
        raise ValidationError(
            {"file": [
                "แนบไฟล์ได้ไม่เกิน "
                f"{settings.LEAVE_ATTACHMENT_MAX_COUNT} ไฟล์ต่อคำร้อง"
            ]}
        )
    return LeaveAttachment.objects.create(
        leave_request=leave_request,
        attachment_type=attachment_type,
        file=uploaded_file,
        original_name=Path(uploaded_file.name).name[:255],
        content_type=(getattr(uploaded_file, "content_type", "") or "")[:100],
        size=uploaded_file.size,
        uploaded_by=uploaded_by,
    )


def delete_leave_attachment(
    leave_request: LeaveRequest,
    attachment: LeaveAttachment,
) -> None:
    if leave_request.status != "draft":
        raise ValidationError(
            {"status": ["ลบไฟล์แนบได้เฉพาะคำร้องที่เป็นแบบร่าง"]}
        )
    attachment.file.delete(save=False)
    attachment.delete()


# ---------------------------------------------------------------------------
# Course review
# ---------------------------------------------------------------------------
REVIEWABLE_STATUSES = {"reviewed", "acknowledged", "rejected"}


def review_course(
    leave_course: LeaveCourse,
    reviewer,
    review_status: str,
    comment: str,
) -> LeaveCourseReview:
    """Record a course-specific review. Never mutates the request's status."""
    profile = getattr(reviewer, "instructor_profile", None)
    if profile is None or not leave_course.course_offering.has_instructor(profile):
        raise PermissionDenied("คุณไม่มีสิทธิ์พิจารณารายวิชานี้")

    request = leave_course.leave_request
    if request.status != "submitted":
        raise ValidationError(
            {"status": ["พิจารณาได้เฉพาะคำร้องที่ส่งแล้วและยังไม่ถูกยกเลิก"]}
        )
    if review_status not in REVIEWABLE_STATUSES:
        raise ValidationError({"review_status": ["ผลการพิจารณาไม่ถูกต้อง"]})
    if review_status == "rejected" and not (comment or "").strip():
        raise ValidationError({"comment": ["กรุณาระบุเหตุผลเมื่อไม่เห็นด้วย"]})

    review = LeaveCourseReview.objects.create(
        leave_course=leave_course,
        reviewer=reviewer,
        review_status=review_status,
        comment=(comment or "").strip(),
    )
    leave_course.review_status = review_status
    leave_course.reviewed_by = reviewer
    leave_course.reviewed_at = review.created_at
    leave_course.save(
        update_fields=["review_status", "reviewed_by", "reviewed_at", "updated_at"]
    )
    return review


# ---------------------------------------------------------------------------
# Attendance projection (read-only)
# ---------------------------------------------------------------------------
def leave_status_map_for_session(session: AttendanceSession) -> dict[str, dict]:
    """Map student_id → displayed leave information for one attendance session.

    Only submitted requests count as a visible leave status. Multiple
    overlapping requests are collapsed to the most recently submitted one and
    counted, so the roster can show "has leave" without duplicating rows.
    """
    student_ids = list(
        session.course_offering.enrollments.filter(
            enrollment_status="enrolled"
        ).values_list("student_id", flat=True)
    )
    if not student_ids:
        return {}

    window_start, window_end = session_time_window(session)
    rows = (
        LeaveCourse.objects.filter(
            course_offering_id=session.course_offering_id,
            leave_request__student_id__in=student_ids,
            leave_request__status="submitted",
            leave_request__start_date__lte=session.session_date,
            leave_request__end_date__gte=session.session_date,
        )
        .select_related(
            "leave_request",
            "leave_request__student",
            "course_offering",
            "course_offering__course",
        )
    )

    grouped: dict[str, list[LeaveCourse]] = {}
    for leave_course in rows:
        request = leave_course.leave_request
        if not _times_overlap(
            request.start_time, request.end_time, window_start, window_end
        ):
            continue
        grouped.setdefault(str(request.student_id), []).append(leave_course)

    result: dict[str, dict] = {}
    for student_id, items in grouped.items():
        items.sort(
            key=lambda item: (
                item.leave_request.submitted_at.timestamp()
                if item.leave_request.submitted_at else 0
            ),
            reverse=True,
        )
        primary = items[0]
        request = primary.leave_request
        result[student_id] = {
            "leave_status": request.status,
            "leave_status_display": request.get_status_display(),
            "leave_type": request.leave_type,
            "leave_type_display": request.get_leave_type_display(),
            "leave_request_id": str(request.id),
            "leave_course_id": str(primary.id),
            "leave_request_count": len(items),
        }
    return result
