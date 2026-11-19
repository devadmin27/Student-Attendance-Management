"""Leave request business logic and attendance read-only projection.

Nothing in this module writes AttendanceRecord/AttendanceSession. The roster
only asks for a leave-status map and displays it alongside (never instead of)
the attendance status (spec §5.2).
"""
from datetime import date, time, timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.accounts.models import StudentProfile
from apps.academics.models import AcademicTerm
from apps.attendance.models import AttendanceSession
from apps.courses.models import Enrollment
from apps.leaves.models import (
    LeaveAttachment,
    LeaveCourse,
    LeaveCourseReview,
    LeavePolicyConfig,
    LeaveRequest,
    LeaveRoleAssignment,
    LeaveWorkflowConfig,
    LeaveWorkflowHistory,
    LeaveWorkflowStep,
)


# ---------------------------------------------------------------------------
# Approval workflow (Phase 2, configurable step order)
# ---------------------------------------------------------------------------
#: Canonical role order. Any configured workflow is an ordered subset of this.
WORKFLOW_ROLE_ORDER = ("advisor", "program_head", "final_approver")
#: Used when no active LeaveWorkflowConfig matches the request.
DEFAULT_WORKFLOW_ROLES = WORKFLOW_ROLE_ORDER
#: (step order, role_type, status while that step is waiting) — default only.
WORKFLOW_STEPS = tuple(
    (order, role, status)
    for order, (role, status) in enumerate(
        (
            ("advisor", "pending_advisor_review"),
            ("program_head", "pending_program_head_review"),
            ("final_approver", "pending_final_approval"),
        ),
        start=1,
    )
)
ROLE_LABELS = {
    "advisor": "อาจารย์ที่ปรึกษา",
    "program_head": "หัวหน้าหน่วยหลักสูตร",
    "final_approver": "ผู้มีอำนาจอนุมัติ",
}
STATUS_FOR_ROLE = {
    "advisor": "pending_advisor_review",
    "program_head": "pending_program_head_review",
    "final_approver": "pending_final_approval",
}
ROLE_FOR_STATUS = {status: role for role, status in STATUS_FOR_ROLE.items()}
PENDING_STATUSES = frozenset(STATUS_FOR_ROLE.values())
IN_FLIGHT_STATUSES = PENDING_STATUSES | {"submitted"}
FINAL_STATUSES = frozenset({"approved", "rejected"})
#: Requests whose leave status must remain visible in the attendance roster.
VISIBLE_ATTENDANCE_STATUSES = IN_FLIGHT_STATUSES | FINAL_STATUSES | {"returned"}

#: Available actions exposed to the SPA (backend still re-checks every call).
ACTION_LABELS = {
    "submit": "ส่งคำร้อง",
    "cancel": "ยกเลิกคำร้อง",
    "resubmit": "ส่งคำร้องอีกครั้ง",
    "advisor_opinion": "บันทึกความเห็นอาจารย์ที่ปรึกษา",
    "program_head_opinion": "บันทึกความเห็นหัวหน้าหน่วยหลักสูตร",
    "final_decision": "บันทึกผลการพิจารณา",
    "approve": "อนุมัติ",
    "reject": "ไม่อนุมัติ",
    "return": "ส่งกลับเพื่อแก้ไข",
    "admin_override": "ผู้ดูแลระบบดำเนินการแทน",
    "legacy_import": "นำเข้าสู่ Workflow",
}


# ---------------------------------------------------------------------------
# Submission policy (Phase 4)
# ---------------------------------------------------------------------------
def resolved_leave_policy() -> dict[str, int]:
    """Day limits from the admin-editable row, with settings as fallback.

    The row is read on every call so an edit in Django admin applies directly.
    If it has been removed, the original settings values keep the system alive.
    """
    config = LeavePolicyConfig.objects.first()
    if config is None:
        return {
            "personal_advance_days": settings.LEAVE_PERSONAL_ADVANCE_DAYS,
            "sick_normal_grace_days": settings.LEAVE_SICK_NORMAL_GRACE_DAYS,
            "sick_late_grace_days": settings.LEAVE_SICK_LATE_GRACE_DAYS,
            "medical_certificate_min_days": (
                settings.LEAVE_MEDICAL_CERTIFICATE_MIN_DAYS
            ),
        }
    return {
        "personal_advance_days": config.personal_advance_days,
        "sick_normal_grace_days": config.sick_normal_grace_days,
        "sick_late_grace_days": config.sick_late_grace_days,
        "medical_certificate_min_days": config.medical_certificate_min_days,
    }


def leave_policy() -> dict:
    """Policy payload for the SPA — day limits come from the resolved policy."""
    return {
        **resolved_leave_policy(),
        "max_attachment_bytes": settings.LEAVE_ATTACHMENT_MAX_BYTES,
        "max_attachment_count": settings.LEAVE_ATTACHMENT_MAX_COUNT,
        "allowed_attachment_extensions": settings.LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS,
        "allowed_attachment_content_types": (
            settings.LEAVE_ATTACHMENT_ALLOWED_CONTENT_TYPES
        ),
        "server_date": timezone.localdate().isoformat(),
    }


#: Fixed rows of the printed "ประวัติการลา" table (paper form has no "other").
HISTORY_LEAVE_TYPES = ("sick", "personal")
HISTORY_LABELS = {
    "sick": "ลาป่วย (วัน)",
    "personal": "ลากิจ (วัน)",
}


def _academic_year_for(day: date) -> int:
    """Academic year (พ.ศ.) covering `day`, from real terms when available."""
    term = (
        AcademicTerm.objects.filter(start_date__lte=day, end_date__gte=day)
        .order_by("-start_date", "-academic_year")
        .first()
    )
    if term is not None:
        return term.academic_year
    # No term covers this date — fall back to the usual Thai-year convention.
    return day.year + 543


def _academic_year_range(year: int) -> tuple[date, date]:
    """Date span of an academic year, from its stored terms when available."""
    spans = list(
        AcademicTerm.objects.filter(academic_year=year).values_list(
            "start_date", "end_date"
        )
    )
    if spans:
        return (
            min(start for start, _ in spans),
            max(end for _, end in spans),
        )
    gregorian_year = year - 543
    return date(gregorian_year, 1, 1), date(gregorian_year, 12, 31)


def _inclusive_days(start: date | None, end: date | None) -> int:
    if not start or not end or end < start:
        return 0
    return (end - start).days + 1


def leave_history_summary(
    student: StudentProfile,
    reference_date: date | None,
    *,
    current: LeaveRequest | None = None,
    exclude_id=None,
    draft: dict | None = None,
) -> list[dict]:
    """Rows for the "ประวัติการลา" table.

    `ลามาแล้ว` counts only approved requests of the same student/type within
    the academic year of `reference_date`, excluding the current request.
    `ลาครั้งนี้` comes from `current` (detail/print) or `draft` (live form
    preview) and is 0 for leave types outside the two paper-form rows.
    """
    reference = reference_date or timezone.localdate()
    year_start, year_end = _academic_year_range(_academic_year_for(reference))

    previous_days = {leave_type: 0 for leave_type in HISTORY_LEAVE_TYPES}
    approved = LeaveRequest.objects.filter(
        student=student,
        status="approved",
        leave_type__in=HISTORY_LEAVE_TYPES,
        start_date__gte=year_start,
        start_date__lte=year_end,
    )
    if current is not None:
        approved = approved.exclude(pk=current.pk)
    elif exclude_id is not None:
        approved = approved.exclude(pk=exclude_id)
    for leave_type, start, end in approved.values_list(
        "leave_type", "start_date", "end_date"
    ):
        previous_days[leave_type] += _inclusive_days(start, end)

    if current is not None:
        current_type = current.leave_type
        current_days = current.total_days
    else:
        draft = draft or {}
        current_type = draft.get("leave_type", "")
        current_days = _inclusive_days(
            draft.get("start_date"), draft.get("end_date")
        )

    return [
        {
            "leave_type": leave_type,
            "label": HISTORY_LABELS[leave_type],
            "previous_days": previous_days[leave_type],
            "current_days": current_days if current_type == leave_type else 0,
        }
        for leave_type in HISTORY_LEAVE_TYPES
    ]


def submission_deadlines(
    leave_type: str,
    start_date: date,
    end_date: date,
    *,
    policy: dict[str, int] | None = None,
) -> tuple[date | None, date | None]:
    """Return (normal deadline, late-grace deadline) for a request.

    - personal: must be filed on or before start_date − advance_days.
    - sick: normal deadline is end_date + normal grace (day after the leave);
      the late-grace deadline is end_date + late grace.
    - other: no timing restriction.

    `policy` lets a caller reuse one resolved snapshot; otherwise it is read
    fresh from `resolved_leave_policy()`.
    """
    policy = policy if policy is not None else resolved_leave_policy()
    if leave_type == "personal":
        return (
            start_date - timedelta(days=policy["personal_advance_days"]),
            None,
        )
    if leave_type == "sick":
        return (
            end_date + timedelta(days=policy["sick_normal_grace_days"]),
            end_date + timedelta(days=policy["sick_late_grace_days"]),
        )
    return None, None


def requires_medical_certificate(
    leave_request: LeaveRequest,
    policy: dict[str, int] | None = None,
) -> bool:
    policy = policy if policy is not None else resolved_leave_policy()
    return (
        leave_request.leave_type == "sick"
        and leave_request.total_days >= policy["medical_certificate_min_days"]
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
    policy = resolved_leave_policy()
    normal_deadline, grace_deadline = submission_deadlines(
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
        policy=policy,
    )
    if leave_request.leave_type == "personal":
        if normal_deadline is not None and today > normal_deadline:
            raise ValidationError(
                {"start_date": [
                    "ลากิจส่วนตัวต้องส่งล่วงหน้าอย่างน้อย "
                    f"{policy['personal_advance_days']} วัน "
                    f"(ภายใน {normal_deadline.strftime('%d/%m/%Y')})"
                ]}
            )
        return

    if grace_deadline is not None and today > grace_deadline:
        raise ValidationError(
            {"end_date": [
                "เลยกำหนดส่งใบลาป่วยแล้ว — ส่งได้ไม่เกิน "
                f"{policy['sick_late_grace_days']} วันหลังวันสิ้นสุดการลา "
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


def validate_medical_certificate(
    leave_request: LeaveRequest,
    policy: dict[str, int] | None = None,
) -> None:
    policy = policy if policy is not None else resolved_leave_policy()
    if not requires_medical_certificate(leave_request, policy=policy):
        return
    if not leave_request.attachments.filter(
        attachment_type="medical_certificate"
    ).exists():
        raise ValidationError(
            {"attachments": [
                "ลาป่วยตั้งแต่ "
                f"{policy['medical_certificate_min_days']} วันขึ้นไป "
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


def _request_term_ids(leave_request: LeaveRequest) -> set:
    return {
        term_id
        for term_id in leave_request.courses.values_list(
            "course_offering__academic_term_id", flat=True
        )
        if term_id is not None
    }


def normalize_workflow_steps(steps) -> tuple[str, ...]:
    """Validate and canonicalise a configured step list.

    Rules: at least one step; every value is a known role; no duplicates; the
    order follows advisor -> program_head -> final_approver; the last step is
    always the final approver.
    """
    if not isinstance(steps, (list, tuple)):
        raise ValidationError({"steps": ["ลำดับขั้นตอนต้องเป็นรายการบทบาท"]})
    cleaned: list[str] = []
    for value in steps:
        role = str(value or "").strip()
        if role not in WORKFLOW_ROLE_ORDER:
            raise ValidationError(
                {"steps": [f"บทบาทใน Workflow ไม่ถูกต้อง: {value}"]}
            )
        if role in cleaned:
            raise ValidationError({"steps": ["ห้ามใช้บทบาทซ้ำใน Workflow"]})
        cleaned.append(role)
    if not cleaned:
        raise ValidationError({"steps": ["ต้องมีขั้นตอนอย่างน้อย 1 ขั้น"]})
    if cleaned[-1] != "final_approver":
        raise ValidationError(
            {"steps": ["ขั้นตอนสุดท้ายต้องเป็นผู้มีอำนาจอนุมัติ"]}
        )
    canonical = [role for role in WORKFLOW_ROLE_ORDER if role in cleaned]
    if cleaned != canonical:
        raise ValidationError(
            {"steps": ["ลำดับขั้นตอนต้องเรียง advisor → program_head → final_approver"]}
        )
    return tuple(cleaned)


def _workflow_scope_rank(config: LeaveWorkflowConfig) -> int:
    """Most specific scope wins: group+term > group > program+term > program > global."""
    if config.class_group_id and config.academic_term_id:
        return 4
    if config.class_group_id:
        return 3
    if config.program_id and config.academic_term_id:
        return 2
    if config.program_id:
        return 1
    return 0


def resolve_workflow_roles(leave_request: LeaveRequest) -> tuple[str, ...]:
    """Pick the ordered roles for this request from LeaveWorkflowConfig.

    Falls back to the default three-step workflow when no active configuration
    matches. Malformed configuration is ignored in favour of the default so a
    bad admin row can never block students from submitting.
    """
    student = leave_request.student
    term_ids = _request_term_ids(leave_request)
    candidates = []
    for config in LeaveWorkflowConfig.objects.filter(is_active=True):
        if config.program_id and config.program_id != student.program_id:
            continue
        if (
            config.class_group_id
            and config.class_group_id != student.class_group_id
        ):
            continue
        if config.academic_term_id and config.academic_term_id not in term_ids:
            continue
        candidates.append(config)
    if not candidates:
        return DEFAULT_WORKFLOW_ROLES
    candidates.sort(
        key=lambda row: (
            _workflow_scope_rank(row),
            row.updated_at or timezone.now(),
        ),
        reverse=True,
    )
    try:
        return normalize_workflow_steps(candidates[0].steps)
    except ValidationError:
        return DEFAULT_WORKFLOW_ROLES


def resolve_assignee(leave_request: LeaveRequest, role_type: str):
    """Resolve the workflow assignee for one role from LeaveRoleAssignment.

    Specificity order (most specific wins):
    class group + term > class group > program + term > program > global.
    Ties are broken by the most recently updated assignment so the result is
    deterministic even if the college keeps replacement rows around.
    """
    student = leave_request.student
    term_ids = _request_term_ids(leave_request)
    candidates = []
    for assignment in LeaveRoleAssignment.objects.filter(
        role_type=role_type, is_active=True, user__is_active=True
    ).select_related("user"):
        if assignment.program_id and assignment.program_id != student.program_id:
            continue
        if (
            assignment.class_group_id
            and assignment.class_group_id != student.class_group_id
        ):
            continue
        if assignment.academic_term_id and assignment.academic_term_id not in term_ids:
            continue
        if (
            assignment.program_id is None
            and assignment.class_group_id is None
            and assignment.academic_term_id is None
            and role_type != "final_approver"
        ):
            # Advisor / program head must be scoped to a programme or group;
            # only the final approver may be a college-wide assignment.
            continue
        candidates.append(assignment)
    if not candidates:
        return None
    candidates.sort(
        key=lambda row: (
            1 if row.class_group_id else 0,
            1 if row.academic_term_id else 0,
            row.updated_at or timezone.now(),
        ),
        reverse=True,
    )
    return candidates[0].user


def workflow_assignees(
    leave_request: LeaveRequest, roles=None
) -> dict:
    """Resolve every configured role, or fail with an actionable message."""
    roles = tuple(roles or resolve_workflow_roles(leave_request))
    assignees = {
        role: resolve_assignee(leave_request, role)
        for role in roles
    }
    missing = [
        ROLE_LABELS[role] for role, user in assignees.items() if user is None
    ]
    if missing:
        raise ValidationError(
            {"workflow": [
                "ยังไม่ได้มอบหมายผู้รับผิดชอบใน Workflow: "
                + ", ".join(missing)
                + " — กรุณาให้ผู้ดูแลระบบกำหนดบทบาทก่อนส่งคำร้อง"
            ]}
        )
    return assignees


def ensure_workflow_steps(
    leave_request: LeaveRequest, assignees: dict, roles=None
) -> None:
    roles = tuple(roles or assignees.keys())
    for order, role in enumerate(roles, start=1):
        LeaveWorkflowStep.objects.update_or_create(
            leave_request=leave_request,
            step_order=order,
            defaults={
                "role_type": role,
                "assignee": assignees[role],
                "status": "pending",
                "acted_by": None,
                "acted_at": None,
                "comment": "",
            },
        )


def _record_history(
    leave_request: LeaveRequest,
    action: str,
    from_status: str,
    to_status: str,
    *,
    actor=None,
    step_order=None,
    role_type: str = "",
    comment: str = "",
) -> LeaveWorkflowHistory:
    return LeaveWorkflowHistory.objects.create(
        leave_request=leave_request,
        step_order=step_order,
        role_type=role_type,
        action=action,
        from_status=from_status,
        to_status=to_status,
        actor=actor,
        comment=comment,
    )


def current_step(leave_request: LeaveRequest):
    """The single step currently waiting for an action (if any)."""
    return (
        leave_request.workflow_steps.filter(status="pending")
        .order_by("step_order")
        .first()
    )


def available_actions(user, leave_request: LeaveRequest) -> list[str]:
    """Actions the SPA may offer — never a substitute for backend checks."""
    if user is None or not getattr(user, "is_authenticated", False):
        return []
    if user.role == "student":
        if leave_request.student.user_id != user.id:
            return []
        actions = []
        if leave_request.is_cancellable:
            actions.append("cancel")
        if leave_request.status == "returned":
            actions.append("resubmit")
        return actions

    actions = []
    step = current_step(leave_request)
    if (
        step is not None
        and step.status == "pending"
        and step.assignee_id == user.id
        and leave_request.status in PENDING_STATUSES
    ):
        if step.role_type in ("advisor", "program_head"):
            actions.extend([f"{step.role_type}_opinion", "return"])
        elif step.role_type == "final_approver":
            actions.append("final_decision")
    if user.role == "admin" and leave_request.status in (
        PENDING_STATUSES | {"returned"}
    ):
        actions.append("admin_override")
    return actions


def _lock_request(leave_request: LeaveRequest) -> LeaveRequest:
    return LeaveRequest.objects.select_for_update().get(pk=leave_request.pk)


def _assert_current_step(leave_request: LeaveRequest, role_type: str, actor):
    expected_status = STATUS_FOR_ROLE[role_type]
    if leave_request.status != expected_status:
        raise ValidationError(
            {"status": ["คำร้องนี้ไม่อยู่ในขั้นตอนที่สามารถดำเนินการได้"]}
        )
    step = leave_request.workflow_steps.filter(
        role_type=role_type, status="pending"
    ).first()
    if step is None:
        raise ValidationError(
            {"workflow": ["ไม่พบขั้นตอนการพิจารณาที่รอดำเนินการ"]}
        )
    if step.assignee_id is None:
        # Legacy rows created before role assignments existed are resolved
        # lazily, but only when a configured assignment now matches.
        resolved = resolve_assignee(leave_request, role_type)
        if resolved is not None:
            step.assignee = resolved
            step.save(update_fields=["assignee", "updated_at"])
    if step.assignee_id != actor.id:
        raise PermissionDenied(
            f"คุณไม่ใช่{ROLE_LABELS[role_type]}ของคำร้องนี้"
        )
    return step


def submit_leave_request(
    leave_request: LeaveRequest, actor=None
) -> LeaveRequest:
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
    # Resolve before opening the transaction so a missing assignment returns a
    # clear 400 rather than a half-created workflow.
    roles = resolve_workflow_roles(leave_request)
    assignees = workflow_assignees(leave_request, roles)

    with transaction.atomic():
        locked = _lock_request(leave_request)
        if locked.status != "draft":
            raise ValidationError({"status": ["ส่งได้เฉพาะคำร้องที่เป็นแบบร่าง"]})
        LeaveWorkflowStep.objects.filter(leave_request=locked).delete()
        ensure_workflow_steps(locked, assignees, roles)
        old_status = locked.status
        locked.status = STATUS_FOR_ROLE[roles[0]]
        locked.submitted_at = timezone.now()
        locked.save(update_fields=["status", "submitted_at", "updated_at"])
        _record_history(
            locked, "submit", old_status, locked.status,
            actor=actor or locked.student.user,
        )
    return locked


def _record_intermediate_opinion(
    leave_request: LeaveRequest,
    actor,
    role_type: str,
    comment: str,
    action: str,
) -> LeaveRequest:
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError(
            {"comment": ["กรุณาบันทึกความเห็นก่อนส่งต่อขั้นตอนถัดไป"]}
        )
    with transaction.atomic():
        locked = _lock_request(leave_request)
        step = _assert_current_step(locked, role_type, actor)
        next_step = (
            locked.workflow_steps.filter(step_order__gt=step.step_order)
            .order_by("step_order")
            .first()
        )
        if next_step is None:
            raise ValidationError(
                {"workflow": ["ไม่พบขั้นตอนถัดไปใน Workflow ของคำร้องนี้"]}
            )
        next_status = STATUS_FOR_ROLE[next_step.role_type]
        old_status = locked.status
        now = timezone.now()
        step.status = "completed"
        step.acted_by = actor
        step.acted_at = now
        step.comment = comment
        step.save(
            update_fields=[
                "status", "acted_by", "acted_at", "comment", "updated_at",
            ]
        )
        locked.status = next_status
        locked.save(update_fields=["status", "updated_at"])
        _record_history(
            locked, action, old_status, next_status,
            actor=actor, step_order=step.step_order,
            role_type=role_type, comment=comment,
        )
    return locked


def record_advisor_opinion(
    leave_request: LeaveRequest, actor, comment: str
) -> LeaveRequest:
    return _record_intermediate_opinion(
        leave_request, actor, "advisor", comment, "advisor_opinion",
    )


def record_program_head_opinion(
    leave_request: LeaveRequest, actor, comment: str
) -> LeaveRequest:
    return _record_intermediate_opinion(
        leave_request, actor, "program_head", comment, "program_head_opinion",
    )


def record_final_decision(
    leave_request: LeaveRequest,
    actor,
    decision: str,
    comment: str,
) -> LeaveRequest:
    decision = (decision or "").strip().lower()
    if decision not in ("approve", "reject"):
        raise ValidationError(
            {"decision": ["ต้องเลือกผลการพิจารณาเป็น approve หรือ reject"]}
        )
    comment = (comment or "").strip()
    if decision == "reject" and not comment:
        raise ValidationError({"comment": ["กรุณาระบุเหตุผลที่ไม่อนุญาต"]})

    with transaction.atomic():
        locked = _lock_request(leave_request)
        step = _assert_current_step(locked, "final_approver", actor)
        old_status = locked.status
        to_status = "approved" if decision == "approve" else "rejected"
        step.status = "completed"
        step.acted_by = actor
        step.acted_at = timezone.now()
        step.comment = comment
        step.save(
            update_fields=[
                "status", "acted_by", "acted_at", "comment", "updated_at",
            ]
        )
        locked.status = to_status
        locked.save(update_fields=["status", "updated_at"])
        _record_history(
            locked, decision, old_status, to_status,
            actor=actor, step_order=step.step_order,
            role_type=step.role_type, comment=comment,
        )
    return locked


def return_for_revision(
    leave_request: LeaveRequest, actor, comment: str
) -> LeaveRequest:
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError(
            {"comment": ["กรุณาระบุเหตุผลที่ส่งกลับเพื่อแก้ไข"]}
        )
    if leave_request.status not in PENDING_STATUSES:
        raise ValidationError(
            {"status": ["ส่งกลับได้เฉพาะคำร้องที่อยู่ระหว่างการพิจารณา"]}
        )
    with transaction.atomic():
        locked = _lock_request(leave_request)
        if locked.status not in PENDING_STATUSES:
            raise ValidationError(
                {"status": ["ส่งกลับได้เฉพาะคำร้องที่อยู่ระหว่างการพิจารณา"]}
            )
        step = current_step(locked)
        if step is None or step.status != "pending":
            raise ValidationError(
                {"workflow": ["ไม่พบขั้นตอนการพิจารณาที่รอดำเนินการ"]}
            )
        if step.role_type == "final_approver":
            raise ValidationError(
                {"status": [
                    "ผู้มีอำนาจอนุมัติต้องบันทึกผลการพิจารณาเป็นอนุญาต "
                    "หรือไม่อนุญาต โดยระบุเหตุผลประกอบ"
                ]}
            )
        if step.assignee_id != actor.id:
            raise PermissionDenied(
                f"คุณไม่ใช่{ROLE_LABELS[step.role_type]}ของคำร้องนี้"
            )
        old_status = locked.status
        step.status = "completed"
        step.acted_by = actor
        step.acted_at = timezone.now()
        step.comment = comment
        step.save(
            update_fields=[
                "status", "acted_by", "acted_at", "comment", "updated_at",
            ]
        )
        locked.status = "returned"
        locked.save(update_fields=["status", "updated_at"])
        _record_history(
            locked, "return", old_status, "returned",
            actor=actor, step_order=step.step_order,
            role_type=step.role_type, comment=comment,
        )
    return locked


def resubmit_leave_request(
    leave_request: LeaveRequest, actor=None
) -> LeaveRequest:
    if leave_request.status != "returned":
        raise ValidationError(
            {"status": ["ส่งคำร้องอีกครั้งได้เฉพาะคำร้องที่ถูกส่งกลับเพื่อแก้ไข"]}
        )
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
    # Timing is intentionally not re-checked: the request was already accepted
    # into the workflow once, and revision must not be blocked by a deadline
    # that has since passed.
    validate_medical_certificate(leave_request)
    roles = resolve_workflow_roles(leave_request)
    assignees = workflow_assignees(leave_request, roles)

    with transaction.atomic():
        locked = _lock_request(leave_request)
        if locked.status != "returned":
            raise ValidationError(
                {"status": ["ส่งคำร้องอีกครั้งได้เฉพาะคำร้องที่ถูกส่งกลับเพื่อแก้ไข"]}
            )
        old_status = locked.status
        LeaveWorkflowStep.objects.filter(leave_request=locked).delete()
        ensure_workflow_steps(locked, assignees, roles)
        locked.status = STATUS_FOR_ROLE[roles[0]]
        locked.save(update_fields=["status", "updated_at"])
        _record_history(
            locked, "resubmit", old_status, locked.status,
            actor=actor or locked.student.user,
        )
    return locked


def cancel_leave_request(
    leave_request: LeaveRequest, actor=None
) -> LeaveRequest:
    if not leave_request.is_cancellable:
        raise ValidationError({"status": ["คำร้องนี้ไม่สามารถยกเลิกได้"]})
    with transaction.atomic():
        locked = _lock_request(leave_request)
        if not locked.is_cancellable:
            raise ValidationError({"status": ["คำร้องนี้ไม่สามารถยกเลิกได้"]})
        old_status = locked.status
        step = current_step(locked)
        pending_steps = list(locked.workflow_steps.filter(status="pending"))
        now = timezone.now()
        for pending in pending_steps:
            pending.status = "skipped"
            pending.acted_by = actor
            pending.acted_at = now
            pending.comment = "ยกเลิกคำร้อง"
            pending.save(
                update_fields=[
                    "status", "acted_by", "acted_at", "comment", "updated_at",
                ]
            )
        locked.status = "cancelled"
        locked.cancelled_at = timezone.now()
        locked.save(update_fields=["status", "cancelled_at", "updated_at"])
        _record_history(
            locked, "cancel", old_status, locked.status,
            actor=actor or locked.student.user,
            step_order=step.step_order if step else None,
            role_type=step.role_type if step else "",
            comment="ยกเลิกคำร้อง",
        )
    return locked


OVERRIDE_TARGET_STATUSES = (
    PENDING_STATUSES | FINAL_STATUSES | {"returned", "cancelled"}
)


def admin_override(
    leave_request: LeaveRequest,
    actor,
    to_status: str,
    comment: str,
) -> LeaveRequest:
    """Admin exception path (§4.6 rule 4) — always requires a reason."""
    if getattr(actor, "role", None) != "admin":
        raise PermissionDenied("เฉพาะผู้ดูแลระบบเท่านั้น")
    comment = (comment or "").strip()
    if not comment:
        raise ValidationError(
            {"comment": ["กรุณาระบุเหตุผลประกอบการดำเนินการของผู้ดูแลระบบ"]}
        )
    if to_status not in OVERRIDE_TARGET_STATUSES:
        raise ValidationError({"to_status": ["สถานะปลายทางไม่ถูกต้อง"]})

    with transaction.atomic():
        locked = _lock_request(leave_request)
        from_status = locked.status
        if from_status in FINAL_STATUSES or from_status == "cancelled":
            raise ValidationError(
                {"status": ["คำร้องที่จบแล้วไม่สามารถดำเนินการแทนได้"]}
            )
        now = timezone.now()
        steps = list(locked.workflow_steps.order_by("step_order"))
        steps_by_role = {step.role_type: step for step in steps}

        if to_status in PENDING_STATUSES:
            target_role = ROLE_FOR_STATUS[to_status]
            target_step = steps_by_role.get(target_role)
            if target_step is None:
                raise ValidationError(
                    {"to_status": ["Workflow ของคำร้องนี้ไม่มีขั้นตอนที่เลือก"]}
                )
            target_order = target_step.step_order
            for step in steps:
                if step.step_order < target_order:
                    if step.status == "pending":
                        step.status = "skipped"
                        step.acted_by = actor
                        step.acted_at = now
                        step.comment = comment
                        step.save(update_fields=[
                            "status", "acted_by", "acted_at", "comment",
                            "updated_at",
                        ])
                elif step.step_order == target_order:
                    step.status = "pending"
                    step.acted_by = None
                    step.acted_at = None
                    step.comment = ""
                    if step.assignee_id is None:
                        resolved = resolve_assignee(locked, step.role_type)
                        if resolved is not None:
                            step.assignee = resolved
                    step.save(update_fields=[
                        "status", "acted_by", "acted_at", "comment",
                        "assignee", "updated_at",
                    ])
                elif step.status != "pending":
                    step.status = "pending"
                    step.acted_by = None
                    step.acted_at = None
                    step.comment = ""
                    step.save(update_fields=[
                        "status", "acted_by", "acted_at", "comment",
                        "updated_at",
                    ])
        else:
            for step in steps:
                if step.status == "pending":
                    step.status = "skipped"
                    step.acted_by = actor
                    step.acted_at = now
                    step.comment = comment
                    step.save(update_fields=[
                        "status", "acted_by", "acted_at", "comment",
                        "updated_at",
                    ])

        if to_status == "cancelled":
            locked.cancelled_at = now
        locked.status = to_status
        update_fields = ["status", "updated_at"]
        if to_status == "cancelled":
            update_fields.append("cancelled_at")
        locked.save(update_fields=update_fields)
        _record_history(
            locked, "admin_override", from_status, to_status,
            actor=actor, comment=comment,
        )
    return locked


def backfill_pending_step_assignees(role_type: str) -> int:
    """Assign unresolved in-flight steps after a role assignment is added."""
    updated = 0
    steps = (
        LeaveWorkflowStep.objects.filter(
            role_type=role_type, status="pending", assignee__isnull=True
        )
        .select_related("leave_request__student")
    )
    for step in steps:
        resolved = resolve_assignee(step.leave_request, role_type)
        if resolved is not None:
            step.assignee = resolved
            step.save(update_fields=["assignee", "updated_at"])
            updated += 1
    return updated



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
    if not leave_request.is_editable:
        raise ValidationError(
            {"status": ["แนบไฟล์ได้เฉพาะคำร้องที่เป็นแบบร่างหรือถูกส่งกลับเพื่อแก้ไข"]}
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
    if not leave_request.is_editable:
        raise ValidationError(
            {"status": ["ลบไฟล์แนบได้เฉพาะคำร้องที่เป็นแบบร่างหรือถูกส่งกลับเพื่อแก้ไข"]}
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
    if request.status in ("draft", "cancelled"):
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

    Submitted, in-flight, and decided requests all count as a visible leave
    status (never draft/cancelled). Multiple overlapping requests are collapsed
    to the most recently submitted one and counted, so the roster can show
    "has leave" without duplicating rows.
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
            leave_request__status__in=VISIBLE_ATTENDANCE_STATUSES,
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
