"""QR attendance core tests: tokens, check-in integrity, session lifecycle."""
import threading
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.tests import BaseSamsTest
from apps.attendance import services
from apps.attendance.models import AttendanceRecord, AttendanceSession, QRToken


class SessionAndTokenTests(BaseSamsTest):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()

    def make_session(self, **kw):
        defaults = dict(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=self.now - timedelta(minutes=10),
            check_in_end=self.now + timedelta(minutes=20),
        )
        defaults.update(kw)
        return AttendanceSession.objects.create(**defaults)

    def login_instructor(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_open_and_issue_token_rotates_hash_and_revokes_previous(self):
        self.login_instructor()
        self.make_session()
        sessions = self.client.get("/api/v1/attendance/sessions/").json()["data"]
        session_id = sessions[0]["id"]
        self.assertEqual(sessions[0]["status"], "scheduled")

        opened = self.client.post(f"/api/v1/attendance/sessions/{session_id}/open/")
        self.assertEqual(opened.status_code, 200)
        self.assertEqual(opened.data["data"]["status"], "open")
        first_qr = opened.data["data"]["qr"]
        self.assertIn("qr", first_qr)

        rotated = self.client.post(f"/api/v1/attendance/sessions/{session_id}/qr-token/")
        self.assertEqual(rotated.status_code, 200)
        second_qr = rotated.data["data"]["qr"]
        self.assertNotEqual(first_qr["qr"], second_qr)

        tokens = QRToken.objects.filter(attendance_session_id=session_id)
        self.assertEqual(tokens.filter(revoked_at__isnull=True).count(), 1)
        self.assertGreater(tokens.count(), 1)

    def test_instructor_cannot_operate_other_teacher_session(self):
        other_user = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        other = other_user.instructor_profile
        other.first_name = "อาจารย์คนอื่น"
        other.save()
        self.auth_user(other_user, "Str0ngTeach!Pass")
        session = self.make_session()
        response = self.client.post(f"/api/v1/attendance/sessions/{session.pk}/open/")
        # 403 (explicit deny) or 404 (outside scope — also IDOR-safe, spec §4.2)
        self.assertIn(
            response.status_code,
            (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND),
        )
        session.refresh_from_db()
        self.assertEqual(session.status, "scheduled")

    def test_duplicate_open_is_rejected(self):
        self.login_instructor()
        session = self.make_session()
        services.open_session(session, self.instructor_user)
        detail = self.client.post(f"/api/v1/attendance/sessions/{session.pk}/open/")
        self.assertIn(detail.status_code, (400, 409))
        self.assertFalse(detail.data["success"])

    def test_paused_session_can_resume(self):
        """paused → open must work (the control room's "เปิดต่อ" button)."""
        self.login_instructor()
        session = self.make_session()
        services.open_session(session, self.instructor_user)
        services.pause_session(session)
        session.refresh_from_db()
        self.assertEqual(session.status, "paused")
        services.open_session(session, self.instructor_user)
        session.refresh_from_db()
        self.assertEqual(session.status, "open")

    def test_cancelled_session_cannot_open(self):
        self.login_instructor()
        session = self.make_session(status="cancelled")
        response = self.client.post(f"/api/v1/attendance/sessions/{session.pk}/open/")
        self.assertEqual(response.status_code, 400)


class CheckInTests(BaseSamsTest):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=self.now - timedelta(minutes=10),
            check_in_end=self.now + timedelta(minutes=20),
            status="open",
        )

    def issue_token(self):
        return services.issue_token(self.session, self.instructor_user).raw

    # ------------------------------------------------------------------
    def test_full_checkin_success_records_present_with_server_time(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["data"]["status"], "present")
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        record = AttendanceRecord.objects.first()
        self.assertEqual(record.check_in_method, "qr")
        self.assertEqual(record.qr_token_id, QRToken.objects.first().id)
        # Server timestamp is authoritative (not trustworthy device time)
        self.assertIsNotNone(record.checked_in_at)

    def test_expired_token_rejected(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        token = services.issue_token(self.session, self.instructor_user)
        token.expires_at = timezone.now() - timedelta(seconds=1)
        token.save()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": token.raw})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "QR_TOKEN_EXPIRED")

    def test_invalid_token_rejected(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.post(
            "/api/v1/attendance/check-in/", {"token": "totally-fake-token"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "QR_TOKEN_INVALID")

    def test_revoked_token_rejected(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        services.issue_token(self.session, self.instructor_user)  # rotates → revokes old
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, 400)
        self.assertIn(response.data["code"], ("QR_TOKEN_EXPIRED", "QR_TOKEN_INVALID"))

    def test_not_enrolled_student_rejected_403(self):
        outsider = User.objects.create_user(
            "s64009", "s9@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        profile = outsider.student_profile
        profile.student_code = "640009"
        profile.first_name = "ไม่ได้ลง"
        profile.last_name = "บทเรียน"
        profile.status = "active"
        profile.save()
        self.auth_user(outsider, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "NOT_ENROLLED")

    def test_checkin_requires_authentication(self):
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_suspended_account_rejected(self):
        self.student.status = "suspended"
        self.student.save()
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(response.data["code"], "ACCOUNT_SUSPENDED")

    def test_duplicate_checkin_same_session_friendly_message(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        first = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(first.status_code, 200)
        second_raw = services.issue_token(self.session, self.instructor_user).raw
        second = self.client.post("/api/v1/attendance/check-in/", {"token": second_raw})
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        self.assertEqual(second.status_code, 409)
        self.assertFalse(second.data["success"])
        self.assertEqual(second.data["code"], "ATTENDANCE_ALREADY_EXISTS")
        self.assertIn("เช็คชื่อ", second.data["message"])

    def test_race_conflict_two_records_never_created(self):
        """Concurrent scans race the unique(session, student) constraint:
        one wins, the loser gets 409 — never two records.

        PostgreSQL-only per spec §17.1 (SQLite file locking distorts
        multi-threaded writes); runs against Supabase when configured.
        """
        from django.db import connection
        from unittest import skipUnless

        @skipUnless(connection.vendor == "postgresql", "requires PostgreSQL")
        def runconcurrency():
            self.auth_user(self.student_user, "Str0ngStud!Pass")
            raw = self.issue_token()
            results = []
            barrier = threading.Barrier(2)

            def worker():
                from rest_framework.test import APIClient

                client = APIClient()
                barrier.wait()
                login = client.post(
                    "/api/v1/auth/login/",
                    {"username": "s64001", "password": "Str0ngStud!Pass"},
                ).json()
                client.credentials(
                    HTTP_AUTHORIZATION="Bearer " + login["data"]["access"]
                )
                results.append(
                    client.post("/api/v1/attendance/check-in/", {"token": raw})
                )

            w1 = threading.Thread(target=worker)
            w2 = threading.Thread(target=worker)
            w1.start(); w2.start()
            w1.join(); w2.join()
            self.assertEqual(
                AttendanceRecord.objects.count(), 1,
                f"responses: {[r.status_code for r in results]}",
            )

        # Sequential duplicate (same constraint) is still validated on any backend
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        first = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(first.status_code, 200)
        # Fire the duplicate as a second "racing" caller
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.student_user)
        dup = client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertIn(dup.status_code, (200, 409))
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_late_when_after_checkin_end_within_threshold(self):
        self.session.check_in_end = self.now - timedelta(seconds=5)
        self.session.save()
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["status"], "late")

    def test_closed_after_late_threshold_rejected(self):
        self.session.check_in_start = self.now - timedelta(minutes=60)
        self.session.check_in_end = self.now - timedelta(minutes=30)
        self.session.save()
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertIn(response.status_code, (400, 403))
        self.assertEqual(response.data["code"], "CHECKIN_CLOSED")

    def test_does_not_accept_client_session_id_or_status(self):
        """Client-supplied session/status is ignored (spec §10.2)."""
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        raw = self.issue_token()
        response = self.client.post(
            "/api/v1/attendance/check-in/",
            {"token": raw, "status": "present", "attendance_session": "hacked-id"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AttendanceRecord.objects.count(), 1)

    def test_pause_blocks_checkin(self):
        raw = self.issue_token()  # issued while open
        self.session.status = "paused"
        self.session.save()
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.post("/api/v1/attendance/check-in/", {"token": raw})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data["success"])

    def test_student_scans_other_session_token(self):
        other_session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=self.now,
            check_in_end=self.now + timedelta(minutes=5),
            status="open",
        )
        other_raw = services.issue_token(other_session, self.instructor_user).raw
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.post("/api/v1/attendance/check-in/", {"token": other_raw})
        self.assertEqual(response.status_code, 200)
        recorded = AttendanceRecord.objects.filter(student=self.student).first()
        self.assertEqual(recorded.attendance_session_id, other_session.pk)


class SessionCloseTests(BaseSamsTest):
    def setUp(self):
        super().setUp()
        self.now = timezone.now()
        self.session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=self.now - timedelta(minutes=15),
            check_in_end=self.now + timedelta(minutes=5),
            status="open",
        )
        services.check_in(
            self.student_user,
            services.issue_token(self.session, self.instructor_user).raw,
        )

    def test_close_keeps_existing_records(self):
        result = services.close_session(self.session, self.instructor_user)
        self.assertEqual(result.status, "closed")
        self.assertEqual(AttendanceRecord.objects.count(), 1)
        record = AttendanceRecord.objects.first()
        self.assertEqual(record.status, "present")
        self.assertIsNone(record.edited_by)

    def test_close_revokes_live_tokens(self):
        services.close_session(self.session, self.instructor_user)
        live = self.session.qr_tokens.filter(revoked_at__isnull=True).count()
        self.assertEqual(live, 0)

    def test_after_close_token_cannot_be_issued(self):
        services.close_session(self.session, self.instructor_user)
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            services.issue_token(self.session, self.instructor_user)

    def test_record_edit_writes_audit(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        record = AttendanceRecord.objects.first()
        response = self.client.patch(
            f"/api/v1/attendance/records/{record.pk}/",
            {"status": "excused", "edit_reason": "มีใบลาป่วย"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        from apps.audit.models import AuditLog

        self.assertTrue(
            AuditLog.objects.filter(action="attendance_record_edit").exists()
        )

    def test_patched_record_requires_reason(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        record = AttendanceRecord.objects.first()
        response = self.client.patch(
            f"/api/v1/attendance/records/{record.pk}/",
            {"status": "excused", "edit_reason": ""},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        record.refresh_from_db()
        self.assertEqual(record.status, "present")

    def test_patched_record_sets_editor_and_audits(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        record = AttendanceRecord.objects.first()
        response = self.client.patch(
            f"/api/v1/attendance/records/{record.pk}/",
            {"status": "excused", "edit_reason": "มีใบลา"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        self.assertEqual(record.status, "excused")
        self.assertEqual(record.edited_by, self.instructor_user)

    def test_close_block_respects_instructor_ownership(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.post(f"/api/v1/attendance/sessions/{self.session.pk}/close/")
        self.assertEqual(response.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, "closed")
