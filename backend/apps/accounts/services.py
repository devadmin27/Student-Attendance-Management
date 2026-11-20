"""Student year-level promotion shared by the group and multi-select actions.

Both entry points build the same per-student plan before any write happens, so
the rules (status, year cap, idempotency) cannot drift between them.
"""
from django.db import transaction

from apps.accounts.models import MAX_ACADEMIC_YEAR_LEVEL
from apps.audit.models import log_audit

STUDYING_STATUS = "studying"

SKIP_MESSAGES = {
    "graduated": "จบการศึกษาแล้ว — ไม่สามารถเลื่อนชั้นได้",
    "withdrawn": "ลาออกแล้ว — ไม่สามารถเลื่อนชั้นได้",
    "leave_of_absence": "พักการเรียนอยู่ — ไม่สามารถเลื่อนชั้นได้",
}


def plan_student(student, expected_year=None):
    """Return one preview/result row; never mutates the student."""
    current = student.academic_year_level
    row = {
        "id": str(student.pk),
        "student_code": student.student_code,
        "student_name": f"{student.first_name} {student.last_name}".strip(),
        "from_year": current,
        "to_year": current + 1,
        "ok": True,
        "skipped": False,
        "code": "",
        "message": "",
    }
    # Order matters: a final-year or non-studying row is always skipped for
    # that concrete reason, even when the caller's expected year is stale.
    if student.status != STUDYING_STATUS:
        row.update(
            ok=False, skipped=True, code="INVALID_STATUS",
            message=SKIP_MESSAGES.get(student.status, "สถานะไม่สามารถเลื่อนชั้นได้"),
        )
        return row
    if current >= MAX_ACADEMIC_YEAR_LEVEL:
        row.update(
            ok=False, skipped=True, code="MAX_YEAR_REACHED",
            message=f"อยู่ชั้นปี {MAX_ACADEMIC_YEAR_LEVEL} ซึ่งเป็นชั้นปีสุดท้ายแล้ว",
        )
        return row
    if expected_year is not None and current != expected_year:
        row.update(
            ok=False, skipped=True, code="YEAR_MISMATCH",
            message=f"ชั้นปีปัจจุบันคือ {current} ไม่ตรงกับ {expected_year} ที่ระบุ (อาจเลื่อนไปแล้ว)",
        )
        return row
    return row


def build_result(rows, *, mode, scope, dry_run):
    succeeded = sum(1 for row in rows if row["ok"] and not row["skipped"])
    skipped = sum(1 for row in rows if row["skipped"])
    return {
        "mode": mode,
        "scope": scope,
        "dry_run": bool(dry_run),
        "requested": len(rows),
        "succeeded": succeeded,
        "skipped": skipped,
        "failed": len(rows) - succeeded - skipped,
        "results": rows,
    }


def apply_promotion(
    *, students, expected_years, groups=(), actor, request,
    mode, reason, scope, dry_run=False,
):
    """Plan every row first, then write them in one transaction.

    ``expected_years`` maps student pk -> the year the caller believes the
    student is in. A mismatch means the batch was already applied (or the data
    changed), so re-running the same request is a safe no-op.
    """
    pairs = [
        (student, plan_student(student, expected_years.get(student.pk)))
        for student in students
    ]
    rows = [row for _, row in pairs]
    payload = build_result(rows, mode=mode, scope=scope, dry_run=dry_run)
    if dry_run:
        return payload

    with transaction.atomic():
        for student, row in pairs:
            if not row["ok"]:
                continue
            old_year = student.academic_year_level
            student.academic_year_level = row["to_year"]
            student.save(update_fields=["academic_year_level", "updated_at"])
            log_audit(
                actor, "student_promote", "student_profile", student.pk,
                metadata={
                    "mode": mode, "scope": scope,
                    "from_year": old_year, "to_year": row["to_year"],
                    "class_group": str(student.class_group_id) if student.class_group_id else None,
                    "reason": reason, "batch": True, "batch_size": len(rows),
                },
                request=request,
            )
        for group in groups:
            if group.academic_year_level >= MAX_ACADEMIC_YEAR_LEVEL:
                continue
            old_year = group.academic_year_level
            group.academic_year_level = old_year + 1
            group.save(update_fields=["academic_year_level", "updated_at"])
            log_audit(
                actor, "class_group_promote", "class_group", group.pk,
                metadata={
                    "mode": mode, "scope": scope,
                    "from_year": old_year, "to_year": group.academic_year_level,
                    "reason": reason, "batch": True,
                },
                request=request,
            )
        log_audit(
            actor, "students_promotion", "student_profile", "",
            metadata={
                "mode": mode, "scope": scope, "reason": reason,
                "requested": payload["requested"],
                "succeeded": payload["succeeded"],
                "skipped": payload["skipped"],
                "failed": payload["failed"],
            },
            request=request,
        )
    return payload
