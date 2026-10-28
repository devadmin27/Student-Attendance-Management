"""QR token issuance/validation and check-in business logic (spec §10).

Security model
--------------
- Tokens are 32-byte random secrets from `secrets`, stored only as SHA-256 hashes.
- Tokens rotate: issuing a new token revokes previous active tokens of the
  session (a UI that polls gets a QR that changes roughly every TTL).
- A session-shared QR token is used by many students, but each student can
  create at most one AttendanceRecord per session — enforced by a unique
  database constraint + race-safe transaction handling.
- Full token values are never logged or stored.
- Limitation (documented, not hidden): rotating a QR does not fully prevent
  real-time re-sharing of a live QR; supplementary measures (rate limits,
  audit logs, manual verification) reduce but do not eliminate that risk.
"""
import hashlib
import secrets

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError as DRFValidationError

from apps.audit.models import log_audit
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    QRToken,
)


class QRTokenExpired(APIException):
    status_code = 400
    default_detail = "QR Code นี้หมดอายุแล้ว กรุณาขอจอแสดงผลใหม่"
    default_code = "QR_TOKEN_EXPIRED"


class QRTokenInvalid(APIException):
    status_code = 400
    default_detail = "QR Code ไม่ถูกต้อง กรุณาสแกนใหม่อีกครั้ง"
    default_code = "QR_TOKEN_INVALID"


class CheckInClosed(APIException):
    status_code = 400
    default_detail = "ช่วงเวลาเช็คชื่อของคาบนี้ปิดแล้ว"
    default_code = "CHECKIN_CLOSED"


class NotEnrolled(APIException):
    status_code = 403
    default_detail = "คุณไม่ได้ลงทะเบียนเรียนในรายวิชานี้"
    default_code = "NOT_ENROLLED"


class AccountSuspended(APIException):
    status_code = 403
    default_detail = "บัญชีของคุณถูกระงับการใช้งาน"
    default_code = "ACCOUNT_SUSPENDED"


class DuplicateAttendance(APIException):
    status_code = 409
    default_detail = "คุณเช็คชื่อในคาบนี้แล้ว"
    default_code = "ATTENDANCE_ALREADY_EXISTS"


def issue_token(session: AttendanceSession, user) -> QRToken:
    """Issue a fresh TTL-limited QR token, revoking previous live tokens."""
    if session.status not in ("open", "scheduled"):
        raise DRFValidationError({"session": ["ปิดรับเช็คชื่อแล้ว — ไม่สามารถออก QR Code ใหม่ได้"]})
    ttl = settings.QR_TOKEN_TTL_SECONDS
    now = timezone.now()
    # Display grace keeps an on-screen QR scannable right up to expiry.
    expires = now + timezone.timedelta(seconds=ttl)
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    with transaction.atomic():
        QRToken.objects.select_for_update().filter(
            attendance_session=session, revoked_at__isnull=True,
            expires_at__gt=now,
        ).update(revoked_at=now)
        token = QRToken.objects.create(
            attendance_session=session,
            token_hash=token_hash,
            issued_by=user if getattr(user, "is_authenticated", False) else None,
            expires_at=expires,
        )
    # `raw` is returned to the view only, never persisted nor logged.
    token.raw = raw_token
    return token


def validate_token(value: str, session_id=None) -> QRToken:
    """Validate a raw token value and return its DB row."""
    if not value or len(value) > 256:
        raise QRTokenInvalid()
    token_hash = hashlib.sha256(value.encode("utf-8")).hexdigest()
    token = QRToken.objects.select_related("attendance_session").filter(
        token_hash=token_hash
    ).first()
    if token is None:
        raise QRTokenInvalid()
    if session_id and str(token.attendance_session_id) != str(session_id):
        raise QRTokenInvalid()
    return token


# ---------------------------------------------------------------------------
# Check-in
# ---------------------------------------------------------------------------
def check_in(user, raw_token: str) -> AttendanceRecord:
    """QR check-in for a student. Applies spec §10.3 validations in order."""
    token = validate_token(raw_token)
    session = token.attendance_session
    if not token.is_valid_now:
        if token.revoked_at is not None:
            raise QRTokenExpired()
        raise QRTokenExpired()

    student_profile = getattr(user, "student_profile", None)
    if student_profile is None:
        raise NotEnrolled()
    if student_profile.status != "active":
        raise AccountSuspended()

    now = timezone.now()
    if session.status == "cancelled":
        raise CheckInClosed("คาบเรียนนี้ถูกยกเลิกแล้ว")
    if not session.is_checkin_open_at(now):
        if session.status == "open":
            raise CheckInClosed()  # outside time window
        raise CheckInClosed()  # paused/closed — same user-facing reason

    offering = session.course_offering
    enrollment = offering.enrollments.filter(
        student=student_profile, enrollment_status="enrolled"
    ).exists()
    if not enrollment:
        raise NotEnrolled()

    # Late rule from Django server time — never from the student's device.
    if session.check_in_end and now > session.check_in_end:
        status = "late"
    else:
        status = "present"

    try:
        with transaction.atomic():
            QRToken.objects.filter(pk=token.pk).update(use_count=F("use_count") + 1)
            record = AttendanceRecord.objects.create(
                attendance_session=session,
                student=student_profile,
                status=status,
                check_in_method="qr",
                qr_token=token,
                source_metadata={"issued_at": token.issued_at.isoformat()},
            )
    except IntegrityError:
        # Unique(session, student) raised — the earlier request wins.
        # Return 409 with the friendly duplicate message (spec §13.2);
        # never create a second record.
        raise DuplicateAttendance()

    log_audit(
        actor=user,
        action="attendance_checkin",
        resource_type="attendance_record",
        resource_id=record.pk,
        metadata={"session": str(session.pk), "status": status, "method": "qr"},
        request=None,
    )
    return record


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------
def open_session(session: AttendanceSession, user) -> AttendanceSession:
    """Open check-in window for a session and issue the first QR token.

    Transitions: scheduled → open (first open), paused → open (resume).
    open → open is rejected as an accidental duplicate open; closed and
    cancelled sessions are terminal.
    """
    if session.status == "open":
        raise DRFValidationError("คาบนี้เปิดรับเช็คชื่ออยู่แล้ว ไม่ควรเปิดซ้ำ")
    if session.status == "cancelled":
        raise DRFValidationError("ไม่สามารถเปิดคาบที่ถูกยกเลิก")
    if session.status == "closed":
        raise DRFValidationError("ไม่สามารถเปิดคาบที่ปิดแล้ว")
    session.status = "open"
    session.save(update_fields=["status", "updated_at"])
    token = issue_token(session, user)
    log_audit(
        actor=user, action="session_open", resource_type="attendance_session",
        resource_id=session.pk, request=None,
    )
    session.current_token = token
    return session


def pause_session(session: AttendanceSession) -> AttendanceSession:
    if session.status != "open":
        raise DRFValidationError("เฉพาะคาบที่เปิดอยู่จึงหยุดชั่วคราวได้")
    session.status = "paused"
    session.save(update_fields=["status", "updated_at"])
    session.qr_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    return session


def close_session(session: AttendanceSession, user) -> AttendanceSession:
    """Close check-in; enrolled students without a record become `absent`.

    Late threshold rule (spec §10.5): records are only created here — after
    the window closed — never before, per the requirement.
    """
    if session.status in ("closed", "cancelled"):
        raise DRFValidationError("คาบนี้ปิดหรือยกเลิกไปแล้ว")
    now = timezone.now()
    with transaction.atomic():
        session.status = "closed"
        session.closed_at = now
        session.save(update_fields=["status", "closed_at", "updated_at"])
        session.qr_tokens.filter(revoked_at__isnull=True).update(revoked_at=now)
        enrolled = session.course_offering.enrollments.filter(
            enrollment_status="enrolled"
        ).select_related("student")
        existing_students = set(
            session.records.values_list("student_id", flat=True)
        )
        missing = [e.student for e in enrolled if e.student_id not in existing_students]
        AttendanceRecord.objects.bulk_create(
            AttendanceRecord(
                attendance_session=session,
                student=s,
                status="absent",
                check_in_method="manual",
                source_metadata={"auto_absent_on_close": True},
            )
            for s in missing
        )
    log_audit(
        actor=user, action="session_close", resource_type="attendance_session",
        resource_id=session.pk, metadata={"absent_created": len(missing)},
        request=None,
    )
    return session


def cancel_session(session: AttendanceSession, user) -> AttendanceSession:
    if session.status in ("cancelled", "closed"):
        raise DRFValidationError("คาบนี้ปิดหรือยกเลิกไปแล้ว")
    session.status = "cancelled"
    session.save(update_fields=["status", "updated_at"])
    session.qr_tokens.filter(revoked_at__isnull=True).update(revoked_at=timezone.now())
    log_audit(
        actor=user, action="session_cancel", resource_type="attendance_session",
        resource_id=session.pk, request=None,
    )
    return session
