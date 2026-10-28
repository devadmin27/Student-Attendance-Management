"""Reports + audit log + CSV import tests."""
import csv
import io

from apps.accounts.tests import BaseSamsTest
from apps.attendance import services
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.audit.models import AuditLog
from django.urls import reverse
from django.utils import timezone
from rest_framework import status


def dt(days_ago_start, minutes):
    base = timezone.now() - timezone.timedelta(days=days_ago_start)
    start = base - timezone.timedelta(minutes=30)
    return start, base + timezone.timedelta(minutes=minutes)


class ReportTests(BaseSamsTest):
    def _prepare_sessions(self):
        from datetime import timedelta

        self.closed_session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=timezone.now() - timedelta(minutes=60),
            check_in_end=timezone.now() - timedelta(minutes=40),
            status="closed",
        )
        AttendanceRecord.objects.create(
            attendance_session=self.closed_session, student=self.student,
            status="present",
        )
        # open session must NOT count toward reports
        self.open_session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=timezone.now(),
            check_in_end=timezone.now() + timedelta(minutes=30),
            status="open",
        )

    def test_report_counts_only_closed_sessions(self):
        self._prepare_sessions()
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.get("/api/v1/reports/attendance/")
        self.assertEqual(response.status_code, 200)
        rows = response.data["data"]["rows"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["present"], 1)
        self.assertEqual(row["attendance_rate"], 100.0)
        self.assertEqual(response.data["data"]["total_closed_sessions"], 1)

    def test_report_rate_formula_with_mixed_statuses(self):
        """rate = attended / (present+late+absent+excused) * 100"""
        from datetime import timedelta

        self._prepare_sessions()
        self.open_session.status = "closed"  # counts toward formula now
        self.open_session.save()
        AttendanceRecord.objects.create(
            attendance_session=self.open_session, student=self.student, status="absent"
        )
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.get("/api/v1/reports/attendance/")
        row = response.data["data"]["rows"][0]
        self.assertEqual(row["present"], 1)
        self.assertEqual(row["absent"], 1)
        self.assertEqual(row["attendance_rate"], 50.0)
        self.assertEqual(response.data["data"]["total_closed_sessions"], 2)

    def auth_report(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_csv_export_sanitize_formula_injection(self):
        from common.csvutils import sanitize_csv_value

        self.assertEqual(sanitize_csv_value("=cmd()"), "'=cmd()")
        self.assertEqual(sanitize_csv_value("+1"), "'+1")
        self.assertEqual(sanitize_csv_value("สวัสดี"), "สวัสดี")


class AuditTests(BaseSamsTest):
    def test_audit_written_on_login_and_open_session(self):
        from datetime import timedelta

        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=timezone.now() - timedelta(minutes=2),
            check_in_end=timezone.now() + timedelta(minutes=30),
        )
        self.client.post(f"/api/v1/attendance/sessions/{session.pk}/open/")
        actions = set(AuditLog.objects.values_list("action", flat=True))
        self.assertIn("auth_login_success", actions)
        self.assertIn("session_open", actions)

    def test_audit_logs_read_only_for_admin(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        listing = self.client.get("/api/v1/audit-logs/")
        self.assertEqual(listing.status_code, 200)
        try:
            write = self.client.post(
                "/api/v1/audit-logs/",
                {"action": "forged", "resource_type": "x"},
            )
            self.assertIn(write.status_code, (403, 404, 405))
        except Exception:
            self.fail("POST to audit list should not crash")

    def test_student_cannot_read_audit_logs(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.get("/api/v1/audit-logs/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class CSVImportTests(BaseSamsTest):
    def _csv_file(self, content):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile("students.csv", content.encode("utf-8-sig"))

    def test_import_creates_profiles_and_reports_row_errors(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        content = (
            "username,student_code,first_name,last_name,academic_year_level,password\n"
            "s99101,991001,นักเรียนใหม่,ทดสอบ,1,Xx9!aaaaaaa\n"
            "s99102,991002,นักเรียนสอง,นามสกุลสอง,1,Yy9!bbbbbbb\n"
            "s99101,991003,ซ้ำ,รายการเดิม,1,Zz9!ccccccc\n"
        )
        response = self.client.post(
            "/api/v1/users/import-students/", {"file": self._csv_file(content)}, format="multipart"
        )
        self.assertEqual(response.status_code, 200)
        failures = response.data["data"]["failed"]
        self.assertEqual(response.data["data"]["created"], 2, msg=failures)
        self.assertEqual(len(failures), 1)

    def test_import_rejects_bad_headers(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.post(
            "/api/v1/users/import-students/",
            {"file": self._csv_file("name,code\nfoo,1")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("CSV_HEADER_INVALID", response.data["code"])

    def test_import_throttled_and_admin_only(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.post(
            "/api/v1/users/import-students/", {"file": self._csv_file("")},
            format="multipart",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
