"""Student leave tests — submission policy, reviews, print, attendance."""
import shutil
import tempfile
from datetime import datetime, time, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.tests import BaseSamsTest
from apps.academics.models import Program
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.audit.models import AuditLog
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.leaves.models import (
    LeaveAttachment,
    LeaveCourse,
    LeaveCourseReview,
    LeaveRequest,
    LeaveRoleAssignment,
    LeaveWorkflowHistory,
    LeaveWorkflowStep,
)
from apps.schedules.models import ClassSchedule


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="sams-leave-tests-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class LeaveTestBase(BaseSamsTest):
    """Base fixture plus a class 09:00–11:00 on a date a week from today.

    Phase 2 approval roles are assigned in `setUpTestData` so that submitting
    a draft always resolves the three workflow steps. Individual tests may
    deactivate or replace an assignment to exercise the missing-assignment
    path.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.advisor_user = User.objects.create_user(
            "advisor1", "advisor1@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        cls.advisor = cls.advisor_user.instructor_profile
        cls.advisor.first_name = "ที่ปรึกษา"
        cls.advisor.last_name = "ทดสอบ"
        cls.advisor.save()

        cls.head_user = User.objects.create_user(
            "head1", "head1@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        cls.head = cls.head_user.instructor_profile
        cls.head.first_name = "หัวหน้า"
        cls.head.last_name = "หลักสูตร"
        cls.head.save()

        cls.approver_user = User.objects.create_user(
            "approver1", "approver1@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        cls.approver = cls.approver_user.instructor_profile
        cls.approver.first_name = "ผู้อนุมัติ"
        cls.approver.last_name = "ทดสอบ"
        cls.approver.save()

        LeaveRoleAssignment.objects.create(
            role_type="advisor", user=cls.advisor_user, program=cls.program
        )
        LeaveRoleAssignment.objects.create(
            role_type="program_head", user=cls.head_user, program=cls.program
        )
        LeaveRoleAssignment.objects.create(
            role_type="final_approver", user=cls.approver_user
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        # Keep test uploads out of the repository's private media volume.
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        # Keep the default leave date comfortably beyond the personal-leave
        # advance window (3 days) so unrelated tests are not timing-dependent.
        self.leave_date = today + timedelta(days=7)
        self.schedule = ClassSchedule.objects.create(
            course_offering=self.offering,
            weekday=self.leave_date.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
            classroom="B-101",
        )
        self.session = self.make_session(self.offering, self.leave_date)

    def make_session(self, offering, day, start=time(9, 0), end=time(11, 0)):
        schedule = offering.schedules.filter(weekday=day.weekday()).first()
        return AttendanceSession.objects.create(
            course_offering=offering,
            class_schedule=schedule,
            instructor=offering.instructor or self.instructor,
            session_date=day,
            check_in_start=timezone.make_aware(datetime.combine(day, start)),
            check_in_end=timezone.make_aware(datetime.combine(day, end)),
            status="closed",
        )

    def make_offering(self, code, weekday=True, instructor=None):
        course = Course.objects.create(
            course_code=code, course_name=f"รายวิชา {code}"
        )
        offering = CourseOffering.objects.create(
            course=course,
            academic_term=self.term,
            instructor=instructor or self.instructor,
            class_group=self.group,
        )
        Enrollment.objects.create(student=self.student, course_offering=offering)
        if weekday:
            ClassSchedule.objects.create(
                course_offering=offering,
                weekday=self.leave_date.weekday(),
                start_time=time(9, 0),
                end_time=time(11, 0),
            )
        return offering

    def create_draft(self, offering_ids=None, **overrides):
        payload = {
            "leave_type": "personal",
            "start_date": self.leave_date.isoformat(),
            "end_date": self.leave_date.isoformat(),
            "reason": "ติดธุระครอบครัว",
            "course_offering_ids": [
                str(pk)
                for pk in ([self.offering.id] if offering_ids is None else offering_ids)
            ],
            **overrides,
        }
        return self.client.post("/api/v1/leave-requests/", payload, format="json")

    def create_submitted(self, offering_ids=None, **overrides):
        draft = self.create_draft(offering_ids=offering_ids, **overrides)
        self.assertEqual(draft.status_code, 201, draft.data)
        response = self.client.post(
            f"/api/v1/leave-requests/{draft.data['data']['id']}/submit/",
            {},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["data"]

    # -- Phase 2 workflow helpers ------------------------------------------
    def advisor_opinion(self, request_id, comment="เห็นควรอนุญาต"):
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        return self.client.post(
            f"/api/v1/leave-approvals/{request_id}/advisor-opinion/",
            {"comment": comment},
            format="json",
        )

    def program_head_opinion(self, request_id, comment="เห็นชอบตามเสนอ"):
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        return self.client.post(
            f"/api/v1/leave-approvals/{request_id}/program-head-opinion/",
            {"comment": comment},
            format="json",
        )

    def final_decision(self, request_id, decision="approve", comment=""):
        self.auth_user(self.approver_user, "Str0ngTeach!Pass")
        return self.client.post(
            f"/api/v1/leave-approvals/{request_id}/final-decision/",
            {"decision": decision, "comment": comment},
            format="json",
        )

    def advance_to_final_approval(self, request_id):
        advisor = self.advisor_opinion(request_id)
        self.assertEqual(advisor.status_code, 200, advisor.data)
        head = self.program_head_opinion(request_id)
        self.assertEqual(head.status_code, 200, head.data)
        return head.data["data"]

    def upload_attachment(
        self,
        request_id,
        name="medical-certificate.pdf",
        content_type="application/pdf",
        attachment_type="medical_certificate",
    ):
        upload = SimpleUploadedFile(
            name, b"%PDF-1.4\nSAMS test certificate\n", content_type=content_type
        )
        return self.client.post(
            f"/api/v1/leave-requests/{request_id}/attachments/",
            {"file": upload, "attachment_type": attachment_type},
            format="multipart",
        )



class LeaveSubmissionTests(LeaveTestBase):
    def test_available_courses_and_single_course_draft(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        available = self.client.get(
            "/api/v1/leave-requests/available-courses/",
            {
                "start_date": self.leave_date.isoformat(),
                "end_date": self.leave_date.isoformat(),
            },
        )
        self.assertEqual(available.status_code, 200)
        row = next(
            item for item in available.data["data"]
            if item["id"] == str(self.offering.id)
        )
        self.assertTrue(row["has_class_in_period"])
        self.assertEqual(row["affected_count"], 1)
        self.assertEqual(row["affected_dates"], [self.leave_date.isoformat()])

        response = self.create_draft()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        body = response.data["data"]
        self.assertEqual(body["status"], "draft")
        self.assertEqual(body["course_count"], 1)
        self.assertEqual(
            body["courses"][0]["affected_start_date"], self.leave_date.isoformat()
        )

    def test_select_more_than_four_courses(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        offerings = [self.offering] + [
            self.make_offering(f"IN20-{index}") for index in range(2, 7)
        ]
        response = self.create_draft([o.id for o in offerings])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["data"]["course_count"], 6)
        self.assertEqual(LeaveCourse.objects.count(), 6)

    def test_course_without_class_in_period_is_flagged_but_selectable(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        no_schedule = self.make_offering("IN20-999", weekday=False)
        available = self.client.get(
            "/api/v1/leave-requests/available-courses/",
            {
                "start_date": self.leave_date.isoformat(),
                "end_date": self.leave_date.isoformat(),
            },
        )
        row = next(
            item for item in available.data["data"]
            if item["id"] == str(no_schedule.id)
        )
        self.assertFalse(row["has_class_in_period"])
        self.assertEqual(row["affected_count"], 0)

        response = self.create_draft([no_schedule.id])
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["data"]["courses"][0]["course_code"], "IN20-999")

    def test_time_window_in_available_courses_excludes_non_overlapping_class(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.get(
            "/api/v1/leave-requests/available-courses/",
            {
                "start_date": self.leave_date.isoformat(),
                "end_date": self.leave_date.isoformat(),
                "start_time": "13:00",
                "end_time": "14:00",
            },
        )
        row = next(
            item for item in response.data["data"]
            if item["id"] == str(self.offering.id)
        )
        self.assertFalse(row["has_class_in_period"])

    def test_submit_requires_course_and_valid_range(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft(offering_ids=[])
        self.assertEqual(draft.status_code, 201, draft.data)
        submit = self.client.post(
            f"/api/v1/leave-requests/{draft.data['data']['id']}/submit/", {}
        )
        self.assertEqual(submit.status_code, 400)

        bad_range = self.create_draft(
            end_date=(self.leave_date - timedelta(days=1)).isoformat()
        )
        self.assertEqual(bad_range.status_code, 400)
        self.assertIn("end_date", bad_range.data["errors"])

        bad_time = self.create_draft(start_time="09:00")
        self.assertEqual(bad_time.status_code, 400)

    def test_submit_then_cancel_and_no_double_submit(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        request_data = self.create_submitted()
        self.assertEqual(request_data["status"], "pending_advisor_review")
        self.assertIsNotNone(request_data["submitted_at"])

        again = self.client.post(
            f"/api/v1/leave-requests/{request_data['id']}/submit/", {}
        )
        self.assertEqual(again.status_code, 400)

        cancelled = self.client.post(
            f"/api/v1/leave-requests/{request_data['id']}/cancel/", {}
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data["data"]["status"], "cancelled")
        self.assertIsNotNone(cancelled.data["data"]["cancelled_at"])

    def test_student_cannot_touch_another_students_request(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        request_data = self.create_submitted()

        other_user = User.objects.create_user(
            "s64002", "s2@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        other = other_user.student_profile
        other.student_code = "640002"
        other.first_name = "อีกคน"
        other.last_name = "ทดสอบ"
        other.save()

        self.auth_user(other_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.get(f"/api/v1/leave-requests/{request_data['id']}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/leave-requests/{request_data['id']}/",
                {"reason": "แก้ข้อมูลผู้อื่น"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-requests/{request_data['id']}/cancel/", {}
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        # Cannot attach a course they are not enrolled in either.
        blocked = self.create_draft([self.offering.id])
        self.assertEqual(blocked.status_code, 400)
        self.assertIn("course_offering_ids", blocked.data["errors"])

    def test_instructor_and_admin_cannot_create_leave_requests(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(self.create_draft().status_code, 403)
        self.assertEqual(
            self.client.get("/api/v1/leave-requests/").status_code, 403
        )

        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        self.assertEqual(self.create_draft().status_code, 403)
        self.assertEqual(
            self.client.get("/api/v1/leave-requests/").status_code, 200
        )


class LeaveSubmissionPolicyTests(LeaveTestBase):
    """Phase 4 — advance/retroactive windows and medical certificates."""

    def _submit(self, request_id):
        return self.client.post(
            f"/api/v1/leave-requests/{request_id}/submit/", {}, format="json"
        )

    def _upload(
        self,
        request_id,
        name="medical-certificate.pdf",
        content_type="application/pdf",
        attachment_type="medical_certificate",
    ):
        upload = SimpleUploadedFile(
            name, b"%PDF-1.4\nSAMS test certificate\n", content_type=content_type
        )
        return self.client.post(
            f"/api/v1/leave-requests/{request_id}/attachments/",
            {"file": upload, "attachment_type": attachment_type},
            format="multipart",
        )

    def test_policy_endpoint_matches_settings(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.get("/api/v1/leave-requests/policy/")
        self.assertEqual(response.status_code, 200, response.data)
        policy = response.data["data"]
        self.assertEqual(policy["personal_advance_days"], 3)
        self.assertEqual(policy["sick_normal_grace_days"], 1)
        self.assertEqual(policy["sick_late_grace_days"], 3)
        self.assertEqual(policy["medical_certificate_min_days"], 3)
        self.assertIn("pdf", policy["allowed_attachment_extensions"])
        self.assertEqual(policy["server_date"], timezone.localdate().isoformat())

        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-requests/policy/").status_code, 200
        )
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-requests/policy/").status_code, 200
        )

    def test_personal_leave_requires_three_days_advance(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        too_soon = today + timedelta(days=2)
        draft = self.create_draft(
            start_date=too_soon.isoformat(), end_date=too_soon.isoformat()
        )
        response = self._submit(draft.data["data"]["id"])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("start_date", response.data["errors"])

        valid = today + timedelta(days=3)
        draft = self.create_draft(
            start_date=valid.isoformat(), end_date=valid.isoformat()
        )
        response = self._submit(draft.data["data"]["id"])
        self.assertEqual(response.status_code, 200, response.data)

    def test_sick_leave_can_be_submitted_by_the_day_after_it_ends(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        draft = self.create_draft(
            leave_type="sick",
            start_date=(today - timedelta(days=2)).isoformat(),
            end_date=(today - timedelta(days=1)).isoformat(),
        )
        response = self._submit(draft.data["data"]["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["status"], "pending_advisor_review")

    def test_sick_leave_grace_period_requires_a_reason(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        start = today - timedelta(days=4)
        end = today - timedelta(days=3)  # normal deadline = today - 2
        draft = self.create_draft(
            leave_type="sick",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        response = self._submit(draft.data["data"]["id"])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("late_submission_reason", response.data["errors"])

        with_reason = self.create_draft(
            leave_type="sick",
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            late_submission_reason="มีไข้สูงและยังเดินทางกลับไม่ไหว",
        )
        response = self._submit(with_reason.data["data"]["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            response.data["data"]["late_submission_reason"],
            "มีไข้สูงและยังเดินทางกลับไม่ไหว",
        )

    def test_sick_leave_beyond_grace_period_is_rejected(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        draft = self.create_draft(
            leave_type="sick",
            start_date=(today - timedelta(days=5)).isoformat(),
            end_date=(today - timedelta(days=4)).isoformat(),
            late_submission_reason="ส่งช้าเกินกำหนด",
        )
        response = self._submit(draft.data["data"]["id"])
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("end_date", response.data["errors"])

    def test_sick_leave_of_three_days_requires_medical_certificate(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        draft = self.create_draft(
            leave_type="sick",
            start_date=(today - timedelta(days=2)).isoformat(),
            end_date=today.isoformat(),
        )
        request_id = draft.data["data"]["id"]

        blocked = self._submit(request_id)
        self.assertEqual(blocked.status_code, 400, blocked.data)
        self.assertIn("attachments", blocked.data["errors"])

        upload = self._upload(request_id)
        self.assertEqual(upload.status_code, 201, upload.data)
        self.assertEqual(
            upload.data["data"]["original_name"], "medical-certificate.pdf"
        )
        self.assertEqual(
            upload.data["data"]["attachment_type"], "medical_certificate"
        )

        response = self._submit(request_id)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.data["data"]["requires_medical_certificate"])
        self.assertTrue(response.data["data"]["medical_certificate_attached"])
        self.assertEqual(len(response.data["data"]["attachments"]), 1)

    def test_attachment_upload_list_delete_and_validation(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        request_id = draft["id"]

        bad = self._upload(
            request_id, name="malware.exe", content_type="application/x-msdownload"
        )
        self.assertEqual(bad.status_code, 400, bad.data)
        self.assertIn("file", bad.data["errors"])

        upload = self._upload(request_id)
        self.assertEqual(upload.status_code, 201, upload.data)
        attachment_id = upload.data["data"]["id"]
        self.assertEqual(LeaveAttachment.objects.count(), 1)

        listed = self.client.get(
            f"/api/v1/leave-requests/{request_id}/attachments/"
        )
        self.assertEqual(listed.status_code, 200, listed.data)
        self.assertEqual(len(listed.data["data"]), 1)
        self.assertEqual(listed.data["data"][0]["id"], attachment_id)

        deleted = self.client.delete(
            f"/api/v1/leave-requests/{request_id}/attachments/{attachment_id}/"
        )
        self.assertEqual(deleted.status_code, 200, deleted.data)
        self.assertEqual(LeaveAttachment.objects.count(), 0)

    def test_submitted_request_cannot_gain_or_lose_attachments(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        request_id = submitted["id"]

        blocked = self._upload(request_id)
        self.assertEqual(blocked.status_code, 400, blocked.data)

        draft = self.create_draft().data["data"]
        upload = self._upload(draft["id"])
        attachment_id = upload.data["data"]["id"]
        self._submit(draft["id"])
        deleted = self.client.delete(
            f"/api/v1/leave-requests/{draft['id']}/attachments/{attachment_id}/"
        )
        self.assertEqual(deleted.status_code, 400, deleted.data)

    def test_attachment_rbac_student_instructor_and_admin(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        upload = self._upload(draft["id"])
        attachment_id = upload.data["data"]["id"]
        download_url = upload.data["data"]["download_url"]
        self.assertEqual(
            download_url,
            f"/leave-requests/{draft['id']}/attachments/{attachment_id}/download/",
        )

        # Owner can download while the request is still a draft.
        own = self.client.get(f"/api/v1{download_url}")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(
            b"".join(own.streaming_content),
            b"%PDF-1.4\nSAMS test certificate\n",
        )

        # Another student cannot see or download it.
        other_user = User.objects.create_user(
            "s64009", "s9@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        other = other_user.student_profile
        other.student_code = "640009"
        other.save()
        self.auth_user(other_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.get(
                f"/api/v1/leave-requests/{draft['id']}/attachments/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.get(f"/api/v1{download_url}").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Drafts stay hidden from instructors.
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get(f"/api/v1{download_url}").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # After submission, the course instructor and an admin can download.
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self._submit(draft["id"])
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        instructor_download = self.client.get(f"/api/v1{download_url}")
        self.assertEqual(instructor_download.status_code, 200)

        second_user = User.objects.create_user(
            "teacher9", "t9@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        self.auth_user(second_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get(f"/api/v1{download_url}").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        self.assertEqual(
            self.client.get(f"/api/v1{download_url}").status_code, 200
        )
        blocked_upload = self._upload(draft["id"])
        self.assertEqual(blocked_upload.status_code, 403, blocked_upload.data)
        self.assertEqual(
            self.client.delete(
                f"/api/v1/leave-requests/{draft['id']}/attachments/{attachment_id}/"
            ).status_code,
            403,
        )

    def test_instructor_inbox_and_print_include_attachments_and_late_reason(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        draft = self.create_draft(
            leave_type="sick",
            start_date=(today - timedelta(days=5)).isoformat(),
            end_date=(today - timedelta(days=3)).isoformat(),
            late_submission_reason="ต้องพักรักษาตัวต่อเนื่อง",
        ).data["data"]
        upload = self._upload(draft["id"])
        self.assertEqual(upload.status_code, 201, upload.data)
        self.assertEqual(self._submit(draft["id"]).status_code, 200)

        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        course_id = draft["courses"][0]["id"]
        inbox = self.client.get(f"/api/v1/leave-courses/{course_id}/")
        self.assertEqual(inbox.status_code, 200, inbox.data)
        self.assertEqual(len(inbox.data["data"]["attachments"]), 1)
        self.assertEqual(
            inbox.data["data"]["late_submission_reason"],
            "ต้องพักรักษาตัวต่อเนื่อง",
        )
        self.assertTrue(inbox.data["data"]["medical_certificate_attached"])

        printed = self.client.get(f"/api/v1/leave-requests/{draft['id']}/print/")
        self.assertEqual(printed.status_code, 200, printed.data)
        document = printed.data["data"]
        self.assertEqual(len(document["attachments"]), 1)
        self.assertEqual(
            document["late_submission_reason"], "ต้องพักรักษาตัวต่อเนื่อง"
        )


class LeaveFormDetailsTests(LeaveTestBase):
    def test_contact_fields_round_trip_and_total_days(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        end = self.leave_date + timedelta(days=2)
        response = self.create_draft(
            start_date=self.leave_date.isoformat(),
            end_date=end.isoformat(),
            contact_phone="08-1234-5678",
            line_id="student01",
            address_during_leave="บ้านเลขที่ 1 ตำบลในเมือง",
            guardian_acknowledged=True,
            guardian_phone="0899999999",
            guardian_address="บ้านเลขที่ 2",
        )
        self.assertEqual(response.status_code, 201, response.data)
        body = response.data["data"]
        self.assertEqual(body["total_days"], 3)
        self.assertEqual(body["contact_phone"], "08-1234-5678")
        self.assertTrue(body["guardian_acknowledged"])
        self.assertEqual(body["student_program_name"], "วิศวกรรมคอมพิวเตอร์")
        self.assertEqual(body["student_class_group_name"], "ห้อง 1")
        self.assertEqual(body["student_year_level"], 1)

        update = self.client.patch(
            f"/api/v1/leave-requests/{body['id']}/",
            {"guardian_acknowledged": False, "contact_phone": "0812345678"},
            format="json",
        )
        self.assertEqual(update.status_code, 200, update.data)
        self.assertFalse(update.data["data"]["guardian_acknowledged"])
        self.assertEqual(update.data["data"]["contact_phone"], "0812345678")

    def test_invalid_phone_numbers_are_rejected(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        for field, payload in (
            ("contact_phone", {"contact_phone": "abc"}),
            ("guardian_phone", {"guardian_phone": "123"}),
        ):
            with self.subTest(field=field):
                response = self.create_draft(**payload)
                self.assertEqual(response.status_code, 400, response.data)
                self.assertIn(field, response.data["errors"])


class LeaveCourseReviewTests(LeaveTestBase):
    def _leave_course_id(self, request_data):
        return request_data["courses"][0]["id"]

    def test_review_is_audited_and_does_not_change_request_status(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        request_data = self.create_submitted()

        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.post(
            f"/api/v1/leave-courses/{self._leave_course_id(request_data)}/review/",
            {"review_status": "reviewed", "comment": "รับทราบการลา"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["review_status"], "reviewed")

        leave_request = LeaveRequest.objects.get(pk=request_data["id"])
        self.assertEqual(leave_request.status, "pending_advisor_review")
        self.assertEqual(LeaveCourseReview.objects.count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(action="leave_course_review").exists()
        )

    def test_rejected_requires_comment(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        request_data = self.create_submitted()
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        url = f"/api/v1/leave-courses/{self._leave_course_id(request_data)}/review/"

        missing = self.client.post(
            url, {"review_status": "rejected", "comment": ""}, format="json"
        )
        self.assertEqual(missing.status_code, 400)
        ok = self.client.post(
            url,
            {"review_status": "rejected", "comment": "ช่วงเวลาดังกล่าวมีสอบ"},
            format="json",
        )
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.data["data"]["review_status"], "rejected")

    def test_draft_is_hidden_from_instructor(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        # Drafts never reach the instructor inbox; they are hidden as 404 so
        # the instructor cannot tell an unseen draft apart from a missing row.
        inbox = self.client.get("/api/v1/leave-courses/")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(len(inbox.data["data"]), 0)
        course_id = self._leave_course_id(draft)
        self.assertEqual(
            self.client.get(f"/api/v1/leave-courses/{course_id}/").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        response = self.client.post(
            f"/api/v1/leave-courses/{course_id}/review/",
            {"review_status": "reviewed", "comment": "ok"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_instructor_scope_and_admin_read_only(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        other_offering = self.make_offering("IN20-777")
        request_data = self.create_submitted([self.offering.id, other_offering.id])
        own_course = next(
            c for c in request_data["courses"]
            if str(c["course_offering"]) == str(self.offering.id)
        )
        other_course = next(
            c for c in request_data["courses"]
            if str(c["course_offering"]) == str(other_offering.id)
        )

        second_user = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        second = second_user.instructor_profile
        second.first_name = "อาจารย์"
        second.last_name = "สอง"
        second.save()
        other_offering.instructor = second
        other_offering.save(update_fields=["instructor"])

        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        inbox = self.client.get("/api/v1/leave-courses/")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(len(inbox.data["data"]), 1)
        self.assertEqual(inbox.data["data"][0]["id"], own_course["id"])
        self.assertEqual(
            self.client.get(
                f"/api/v1/leave-courses/{other_course['id']}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-courses/{own_course['id']}/review/",
                {"review_status": "reviewed", "comment": "เห็นควรอนุโลม"},
                format="json",
            ).status_code,
            200,
        )

        # Co-instructor of the same offering can access and review too.
        self.offering.instructors.add(second)
        self.auth_user(second_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get(f"/api/v1/leave-courses/{own_course['id']}/").status_code,
            200,
        )

        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        self.assertEqual(self.client.get("/api/v1/leave-courses/").status_code, 200)
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-courses/{own_course['id']}/review/",
                {"review_status": "reviewed", "comment": "admin"},
                format="json",
            ).status_code,
            403,
        )

    def test_student_cannot_use_course_inbox(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-courses/").status_code, 403
        )


class LeaveAttendanceIntegrationTests(LeaveTestBase):
    def _roster(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.get(
            f"/api/v1/attendance/sessions/{self.session.id}/roster/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["data"][0]

    def test_roster_shows_submitted_leave_without_touching_attendance(self):
        AttendanceRecord.objects.create(
            attendance_session=self.session,
            student=self.student,
            status="absent",
            check_in_method="manual",
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.create_submitted()

        row = self._roster()
        self.assertEqual(row["checked_in_status"], "absent")
        self.assertEqual(row["leave_status"], "pending_advisor_review")
        self.assertEqual(row["leave_type"], "personal")
        self.assertEqual(row["leave_request_count"], 1)

        record = AttendanceRecord.objects.get(
            attendance_session=self.session, student=self.student
        )
        self.assertEqual(record.status, "absent")

    def test_leave_outside_time_window_is_not_shown(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.create_submitted(start_time="13:00", end_time="14:00")
        row = self._roster()
        self.assertIsNone(row["leave_status"])

        request_data = LeaveRequest.objects.get()
        request_data.start_time = None
        request_data.end_time = None
        request_data.save(update_fields=["start_time", "end_time"])
        row = self._roster()
        self.assertEqual(row["leave_status"], "pending_advisor_review")

    def test_cancelled_or_draft_leave_is_not_shown(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        row = self._roster()
        self.assertIsNone(row["leave_status"])

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        row = self._roster()
        self.assertEqual(row["leave_status"], "pending_advisor_review")

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.client.post(f"/api/v1/leave-requests/{submitted['id']}/cancel/", {})
        row = self._roster()
        self.assertIsNone(row["leave_status"])
        self.assertTrue(LeaveRequest.objects.filter(pk=draft["id"]).exists())

    def test_overlapping_requests_counted_once_per_student(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.create_submitted()
        self.create_submitted(reason="คำร้องที่สอง")
        row = self._roster()
        self.assertEqual(row["leave_status"], "pending_advisor_review")
        self.assertEqual(row["leave_request_count"], 2)

    def test_other_offering_leave_does_not_appear(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        other = self.make_offering("IN20-888")
        self.create_submitted([other.id])
        row = self._roster()
        self.assertIsNone(row["leave_status"])


class LeavePrintTests(LeaveTestBase):
    def _print(self, request_id):
        return self.client.get(f"/api/v1/leave-requests/{request_id}/print/")

    def test_student_can_print_own_request_only(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()

        response = self._print(submitted["id"])
        self.assertEqual(response.status_code, 200, response.data)
        document = response.data["data"]
        self.assertEqual(document["scope"], "full")
        self.assertEqual(document["student_code"], "640001")
        self.assertEqual(document["status_display"], "รอความเห็นอาจารย์ที่ปรึกษา")
        self.assertTrue(document["generated_at"])
        self.assertEqual(len(document["courses"]), 1)
        self.assertTrue(document["courses"][0]["instructor_names"])

        other_user = User.objects.create_user(
            "s64003", "s3@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        other = other_user.student_profile
        other.student_code = "640003"
        other.save()
        self.auth_user(other_user, "Str0ngStud!Pass")
        self.assertEqual(
            self._print(submitted["id"]).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_admin_can_print_any_request(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()

        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self._print(submitted["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["scope"], "full")
        self.assertEqual(len(response.data["data"]["courses"]), 1)

    def test_instructor_print_is_course_scoped_and_hides_drafts(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        second_user = User.objects.create_user(
            "teacher3", "t3@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        second = second_user.instructor_profile
        second.first_name = "อาจารย์"
        second.last_name = "สาม"
        second.save()
        other_offering = self.make_offering("IN20-777", instructor=second)
        submitted = self.create_submitted([self.offering.id, other_offering.id])

        # Instructor 1 sees only their own course block.
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self._print(submitted["id"])
        self.assertEqual(response.status_code, 200, response.data)
        document = response.data["data"]
        self.assertEqual(document["scope"], "course")
        self.assertEqual(len(document["courses"]), 1)
        self.assertEqual(document["courses"][0]["course_code"], "IN20-111")

        # Instructor 2 sees only the other course block.
        self.auth_user(second_user, "Str0ngTeach!Pass")
        response = self._print(submitted["id"])
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [c["course_code"] for c in response.data["data"]["courses"]],
            ["IN20-777"],
        )

        # An unrelated request is not printable.
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        own_only = self.create_submitted()
        self.auth_user(second_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self._print(own_only["id"]).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # Drafts never render for instructors.
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self._print(draft["id"]).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_print_includes_contact_guardian_and_identity_details(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        end = self.leave_date + timedelta(days=1)
        submitted = self.create_submitted(
            start_date=self.leave_date.isoformat(),
            end_date=end.isoformat(),
            contact_phone="0812345678",
            line_id="student01",
            address_during_leave="บ้านเลขที่ 9 ตำบลทับเที่ยง",
            guardian_acknowledged=True,
            guardian_phone="0898887777",
            guardian_address="บ้านเลขที่ 10 อำเภอเมือง",
        )

        response = self._print(submitted["id"])
        self.assertEqual(response.status_code, 200, response.data)
        document = response.data["data"]
        self.assertEqual(document["total_days"], 2)
        self.assertEqual(document["contact_phone"], "0812345678")
        self.assertEqual(document["line_id"], "student01")
        self.assertEqual(
            document["address_during_leave"], "บ้านเลขที่ 9 ตำบลทับเที่ยง"
        )
        self.assertTrue(document["guardian_acknowledged"])
        self.assertEqual(document["guardian_phone"], "0898887777")
        self.assertEqual(
            document["guardian_address"], "บ้านเลขที่ 10 อำเภอเมือง"
        )
        self.assertEqual(document["student_program_name"], "วิศวกรรมคอมพิวเตอร์")
        self.assertEqual(document["student_class_group_name"], "ห้อง 1")
        self.assertEqual(document["student_year_level"], 1)

    def test_print_requires_login(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        self.client.credentials()
        response = self._print(submitted["id"])
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )


class LeaveWorkflowSubmissionTests(LeaveTestBase):
    """Phase 2 — submitting a draft creates the three-step workflow."""

    def test_submit_creates_steps_assignees_history_and_actions(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()

        self.assertEqual(submitted["status"], "pending_advisor_review")
        self.assertEqual(
            [step["role_type"] for step in submitted["workflow_steps"]],
            ["advisor", "program_head", "final_approver"],
        )
        self.assertEqual(
            [str(step["assignee"]) for step in submitted["workflow_steps"]],
            [
                str(self.advisor_user.id),
                str(self.head_user.id),
                str(self.approver_user.id),
            ],
        )
        self.assertTrue(
            all(step["status"] == "pending" for step in submitted["workflow_steps"])
        )
        self.assertEqual(submitted["current_step"]["role_type"], "advisor")
        self.assertEqual(submitted["workflow_history"][-1]["action"], "submit")
        self.assertEqual(
            submitted["workflow_history"][-1]["actor"], self.student_user.id
        )
        self.assertIn("cancel", submitted["available_actions"])
        self.assertNotIn("resubmit", submitted["available_actions"])
        self.assertTrue(AuditLog.objects.filter(action="leave_submit").exists())
        self.assertEqual(LeaveWorkflowStep.objects.count(), 3)

    def test_submit_is_blocked_when_a_role_assignment_is_missing(self):
        LeaveRoleAssignment.objects.filter(role_type="program_head").update(
            is_active=False
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        response = self.client.post(
            f"/api/v1/leave-requests/{draft['id']}/submit/", {}, format="json"
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("workflow", response.data["errors"])
        self.assertIn(
            "หัวหน้าหน่วยหลักสูตร", response.data["errors"]["workflow"][0]
        )
        stored = LeaveRequest.objects.get(pk=draft["id"])
        self.assertEqual(stored.status, "draft")
        self.assertEqual(stored.workflow_steps.count(), 0)

    def test_more_specific_class_group_assignment_wins(self):
        specific = User.objects.create_user(
            "advisor-group", "ag@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        specific.instructor_profile.first_name = "ที่ปรึกษาเฉพาะกลุ่ม"
        specific.instructor_profile.save()
        LeaveRoleAssignment.objects.create(
            role_type="advisor",
            user=specific,
            program=self.program,
            class_group=self.group,
        )

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        advisor_step = next(
            step for step in submitted["workflow_steps"]
            if step["role_type"] == "advisor"
        )
        self.assertEqual(advisor_step["assignee"], specific.id)

    def test_sick_request_sets_assignees_as_well(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        today = timezone.localdate()
        submitted = self.create_submitted(
            leave_type="sick",
            start_date=(today - timedelta(days=1)).isoformat(),
            end_date=today.isoformat(),
        )
        self.assertEqual(submitted["status"], "pending_advisor_review")
        self.assertEqual(len(submitted["workflow_steps"]), 3)


class LeaveWorkflowApprovalTests(LeaveTestBase):
    """Phase 2 — sequential approval, RBAC, return/resubmit, admin override."""

    def setUp(self):
        super().setUp()
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.request_data = self.create_submitted()
        self.request_id = self.request_data["id"]

    def test_full_approval_flow_in_order(self):
        advisor = self.advisor_opinion(self.request_id, "เห็นควรอนุญาต")
        self.assertEqual(advisor.status_code, 200, advisor.data)
        body = advisor.data["data"]
        self.assertEqual(body["status"], "pending_program_head_review")
        self.assertEqual(body["workflow_steps"][0]["status"], "completed")
        self.assertEqual(body["workflow_steps"][0]["acted_by"], self.advisor_user.id)

        # The programme head now sees the new action set.
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        head_view = self.client.get(f"/api/v1/leave-approvals/{self.request_id}/")
        self.assertEqual(head_view.status_code, 200, head_view.data)
        self.assertIn("program_head_opinion", head_view.data["data"]["available_actions"])
        self.assertIn("return", head_view.data["data"]["available_actions"])

        head = self.program_head_opinion(self.request_id, "เห็นชอบตามเสนอ")
        self.assertEqual(head.status_code, 200, head.data)
        body = head.data["data"]
        self.assertEqual(body["status"], "pending_final_approval")
        self.assertEqual(body["workflow_steps"][0]["status"], "completed")
        self.assertEqual(body["workflow_steps"][1]["status"], "completed")

        self.auth_user(self.approver_user, "Str0ngTeach!Pass")
        approver_view = self.client.get(f"/api/v1/leave-approvals/{self.request_id}/")
        self.assertEqual(approver_view.status_code, 200, approver_view.data)
        self.assertIn(
            "final_decision", approver_view.data["data"]["available_actions"]
        )

        final = self.final_decision(self.request_id, "approve", "อนุญาต")
        self.assertEqual(final.status_code, 200, final.data)
        body = final.data["data"]
        self.assertEqual(body["status"], "approved")
        self.assertEqual(
            [step["status"] for step in body["workflow_steps"]],
            ["completed", "completed", "completed"],
        )
        self.assertEqual(
            [entry["action"] for entry in body["workflow_history"]],
            ["submit", "advisor_opinion", "program_head_opinion", "approve"],
        )
        self.assertEqual(body["workflow_history"][-1]["actor"], self.approver_user.id)
        self.assertNotIn("cancel", body["available_actions"])

        for action in (
            "leave_submit",
            "leave_advisor_opinion",
            "leave_program_head_opinion",
            "leave_final_decision",
        ):
            self.assertTrue(AuditLog.objects.filter(action=action).exists(), action)

    def test_steps_cannot_be_skipped_and_unrelated_staff_cannot_act(self):
        # The programme head cannot act during the advisor step.
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        early = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/program-head-opinion/",
            {"comment": "ข้ามขั้นตอน"},
            format="json",
        )
        self.assertEqual(early.status_code, 400, early.data)

        # The final approver cannot decide before both opinions exist.
        self.auth_user(self.approver_user, "Str0ngTeach!Pass")
        early = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/final-decision/",
            {"decision": "approve"},
            format="json",
        )
        self.assertEqual(early.status_code, 400, early.data)

        # An instructor who is not an assignee cannot even see the request.
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get(
                f"/api/v1/leave-approvals/{self.request_id}/"
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-approvals/{self.request_id}/advisor-opinion/",
                {"comment": "ไม่ใช่ที่ปรึกษา"},
                format="json",
            ).status_code,
            status.HTTP_404_NOT_FOUND,
        )

        # The assigned advisor still cannot act out of turn once advanced.
        self.assertEqual(self.advisor_opinion(self.request_id).status_code, 200)
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        again = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/advisor-opinion/",
            {"comment": "ซ้ำ"},
            format="json",
        )
        self.assertEqual(again.status_code, 400, again.data)

    def test_intermediate_opinion_requires_a_comment(self):
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        response = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/advisor-opinion/",
            {"comment": "   "},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("comment", response.data["errors"])

    def test_reject_requires_reason_and_marks_all_steps(self):
        self.advance_to_final_approval(self.request_id)

        missing = self.final_decision(self.request_id, "reject", "")
        self.assertEqual(missing.status_code, 400, missing.data)
        self.assertIn("comment", missing.data["errors"])

        rejected = self.final_decision(
            self.request_id, "reject", "เอกสารไม่ครบตามระเบียบ"
        )
        self.assertEqual(rejected.status_code, 200, rejected.data)
        body = rejected.data["data"]
        self.assertEqual(body["status"], "rejected")
        self.assertEqual(body["workflow_steps"][-1]["comment"], "เอกสารไม่ครบตามระเบียบ")
        self.assertTrue(AuditLog.objects.filter(action="leave_final_decision").exists())

    def test_return_for_revision_then_edit_and_resubmit(self):
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        returned = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/return/",
            {"comment": "กรุณาแนบใบรับรองแพทย์"},
            format="json",
        )
        self.assertEqual(returned.status_code, 200, returned.data)
        self.assertEqual(returned.data["data"]["status"], "returned")

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        detail = self.client.get(f"/api/v1/leave-requests/{self.request_id}/")
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertTrue(detail.data["data"]["is_editable"])
        self.assertIn("resubmit", detail.data["data"]["available_actions"])
        self.assertIn("cancel", detail.data["data"]["available_actions"])

        edited = self.client.patch(
            f"/api/v1/leave-requests/{self.request_id}/",
            {"reason": "แก้ไขเหตุผลตามคำแนะนำ"},
            format="json",
        )
        self.assertEqual(edited.status_code, 200, edited.data)

        upload = self.upload_attachment(self.request_id)
        self.assertEqual(upload.status_code, 201, upload.data)

        resubmitted = self.client.post(
            f"/api/v1/leave-requests/{self.request_id}/resubmit/", {}
        )
        self.assertEqual(resubmitted.status_code, 200, resubmitted.data)
        body = resubmitted.data["data"]
        self.assertEqual(body["status"], "pending_advisor_review")
        self.assertEqual(
            [step["status"] for step in body["workflow_steps"]],
            ["pending", "pending", "pending"],
        )
        self.assertTrue(
            all(step["acted_by"] is None for step in body["workflow_steps"])
        )
        self.assertEqual(
            [entry["action"] for entry in body["workflow_history"]],
            ["submit", "return", "resubmit"],
        )
        self.assertTrue(AuditLog.objects.filter(action="leave_resubmit").exists())

    def test_final_approver_cannot_send_back(self):
        self.advance_to_final_approval(self.request_id)
        self.auth_user(self.approver_user, "Str0ngTeach!Pass")
        response = self.client.post(
            f"/api/v1/leave-approvals/{self.request_id}/return/",
            {"comment": "ขอให้แก้ไข"},
            format="json",
        )
        self.assertEqual(response.status_code, 400, response.data)

    def test_cancel_during_review_skips_all_pending_steps(self):
        self.assertEqual(self.advisor_opinion(self.request_id).status_code, 200)

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        cancelled = self.client.post(
            f"/api/v1/leave-requests/{self.request_id}/cancel/", {}
        )
        self.assertEqual(cancelled.status_code, 200, cancelled.data)
        body = cancelled.data["data"]
        self.assertEqual(body["status"], "cancelled")
        self.assertEqual(body["workflow_steps"][0]["status"], "completed")
        self.assertEqual(body["workflow_steps"][1]["status"], "skipped")
        self.assertEqual(body["workflow_steps"][2]["status"], "skipped")
        self.assertNotIn("cancel", body["available_actions"])

        # A cancelled request is no longer actionable and leaves the inbox.
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-approvals/").data["data"], []
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-requests/{self.request_id}/cancel/", {}
            ).status_code,
            400,
        )

    def test_cannot_cancel_after_final_decision(self):
        self.advance_to_final_approval(self.request_id)
        self.assertEqual(
            self.final_decision(self.request_id, "approve", "อนุมัติ").status_code, 200
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-requests/{self.request_id}/cancel/", {}
            ).status_code,
            400,
        )

    def test_approval_inbox_is_scoped_to_the_current_step(self):
        # Step 1: only the advisor (and admin) sees the request.
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        self.assertEqual(len(self.client.get("/api/v1/leave-approvals/").data["data"]), 1)
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        self.assertEqual(self.client.get("/api/v1/leave-approvals/").data["data"], [])
        self.auth_user(self.approver_user, "Str0ngTeach!Pass")
        self.assertEqual(self.client.get("/api/v1/leave-approvals/").data["data"], [])
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        self.assertEqual(len(self.client.get("/api/v1/leave-approvals/").data["data"]), 1)

        # Step 2: the inbox moves to the programme head.
        self.assertEqual(self.advisor_opinion(self.request_id).status_code, 200)
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        self.assertEqual(self.client.get("/api/v1/leave-approvals/").data["data"], [])
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        self.assertEqual(len(self.client.get("/api/v1/leave-approvals/").data["data"]), 1)

        # Students never get an approval inbox.
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-approvals/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_admin_override_requires_reason_and_audit_trail(self):
        self.assertEqual(self.advisor_opinion(self.request_id).status_code, 200)

        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        missing = self.client.post(
            f"/api/v1/leave-requests/{self.request_id}/admin-override/",
            {"to_status": "approved", "comment": ""},
            format="json",
        )
        self.assertEqual(missing.status_code, 400, missing.data)

        overridden = self.client.post(
            f"/api/v1/leave-requests/{self.request_id}/admin-override/",
            {
                "to_status": "approved",
                "comment": "ผู้ดูแลระบบอนุมัติแทนเนื่องจากผู้รับผิดชอบไม่ว่าง",
            },
            format="json",
        )
        self.assertEqual(overridden.status_code, 200, overridden.data)
        body = overridden.data["data"]
        self.assertEqual(body["status"], "approved")
        self.assertEqual(body["workflow_steps"][1]["status"], "skipped")
        self.assertEqual(body["workflow_steps"][2]["status"], "skipped")
        self.assertEqual(body["workflow_history"][-1]["action"], "admin_override")
        self.assertEqual(
            body["workflow_history"][-1]["actor"], self.admin_user.id
        )
        self.assertTrue(AuditLog.objects.filter(action="leave_admin_override").exists())

        # A finished request can no longer be overridden.
        again = self.client.post(
            f"/api/v1/leave-requests/{self.request_id}/admin-override/",
            {"to_status": "rejected", "comment": "เปลี่ยนผล"},
            format="json",
        )
        self.assertEqual(again.status_code, 400, again.data)

    def test_non_admin_cannot_use_admin_override(self):
        self.auth_user(self.head_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-requests/{self.request_id}/admin-override/",
                {"to_status": "approved", "comment": "ข้ามขั้น"},
                format="json",
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )


class LeaveRoleAssignmentTests(LeaveTestBase):
    """Phase 2 — admin-managed workflow roles."""

    def test_only_admin_manages_assignments(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-role-assignments/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        self.assertEqual(
            self.client.get("/api/v1/leave-role-assignments/").status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.get("/api/v1/leave-role-assignments/")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(len(response.data["data"]), 3)

    def test_assignment_validation_rules(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")

        # Advisor / programme head must be instructor accounts.
        bad_user = self.client.post(
            "/api/v1/leave-role-assignments/",
            {
                "role_type": "advisor",
                "user": str(self.student_user.id),
                "program": str(self.program.id),
            },
            format="json",
        )
        self.assertEqual(bad_user.status_code, 400, bad_user.data)
        self.assertIn("user", bad_user.data["errors"])

        # A programme head must be scoped to a programme.
        no_program = self.client.post(
            "/api/v1/leave-role-assignments/",
            {"role_type": "program_head", "user": str(self.head_user.id)},
            format="json",
        )
        self.assertEqual(no_program.status_code, 400, no_program.data)
        self.assertIn("program", no_program.data["errors"])

        # Duplicate active scope is rejected.
        duplicate = self.client.post(
            "/api/v1/leave-role-assignments/",
            {
                "role_type": "advisor",
                "user": str(self.advisor_user.id),
                "program": str(self.program.id),
            },
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400, duplicate.data)
        self.assertIn("role_type", duplicate.data["errors"])

        # Class group must belong to the selected programme.
        other_program = Program.objects.create(
            program_code="ME", program_name="วิศวกรรมเครื่องกล"
        )
        mismatch = self.client.post(
            "/api/v1/leave-role-assignments/",
            {
                "role_type": "advisor",
                "user": str(self.advisor_user.id),
                "program": str(other_program.id),
                "class_group": str(self.group.id),
            },
            format="json",
        )
        self.assertEqual(mismatch.status_code, 400, mismatch.data)
        self.assertIn("class_group", mismatch.data["errors"])

        # The final approver may be a global admin assignment.
        final = LeaveRoleAssignment.objects.get(role_type="final_approver")
        updated = self.client.patch(
            f"/api/v1/leave-role-assignments/{final.id}/",
            {"user": str(self.admin_user.id)},
            format="json",
        )
        self.assertEqual(updated.status_code, 200, updated.data)
        self.assertEqual(updated.data["user"], self.admin_user.id)

    def test_creating_assignment_backfills_unresolved_pending_steps(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        LeaveWorkflowStep.objects.filter(
            leave_request_id=submitted["id"], role_type="program_head"
        ).update(assignee=None)
        LeaveRoleAssignment.objects.filter(role_type="program_head").update(
            is_active=False
        )

        replacement = User.objects.create_user(
            "head2", "head2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        created = self.client.post(
            "/api/v1/leave-role-assignments/",
            {
                "role_type": "program_head",
                "user": str(replacement.id),
                "program": str(self.program.id),
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        step = LeaveWorkflowStep.objects.get(
            leave_request_id=submitted["id"], role_type="program_head"
        )
        self.assertEqual(step.assignee_id, replacement.id)
        self.assertTrue(
            AuditLog.objects.filter(
                action="leave_role_assignment_create"
            ).exists()
        )

    def test_legacy_submitted_request_can_be_progressed_after_assignment(self):
        """Phase 1 rows upgraded by migration 0004 (status submitted)."""
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        request = LeaveRequest.objects.get(pk=draft["id"])
        request.status = "submitted"
        request.submitted_at = timezone.now()
        request.save(update_fields=["status", "submitted_at"])
        for order, role in (
            (1, "advisor"), (2, "program_head"), (3, "final_approver")
        ):
            LeaveWorkflowStep.objects.create(
                leave_request=request, step_order=order, role_type=role,
                status="pending",
            )

        # The migrations have no assignee snapshot; creating an assignment
        # resolves the legacy step so the advisor can act on it.
        LeaveRoleAssignment.objects.filter(role_type="advisor").update(
            is_active=False
        )
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        created = self.client.post(
            "/api/v1/leave-role-assignments/",
            {
                "role_type": "advisor",
                "user": str(self.advisor_user.id),
                "program": str(self.program.id),
            },
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        step = LeaveWorkflowStep.objects.get(
            leave_request=request, role_type="advisor"
        )
        self.assertEqual(step.assignee_id, self.advisor_user.id)

        # The request is still visible in the student's attendance roster.
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        roster = self.client.get(
            f"/api/v1/attendance/sessions/{self.session.id}/roster/"
        )
        self.assertEqual(roster.status_code, 200, roster.data)
        self.assertEqual(roster.data["data"][0]["leave_status"], "submitted")


class LeaveWorkflowAttendanceTests(LeaveTestBase):
    """Phase 2 — leave status stays informational for attendance."""

    def test_roster_reflects_workflow_status_without_changing_attendance(self):
        AttendanceRecord.objects.create(
            attendance_session=self.session,
            student=self.student,
            status="absent",
            check_in_method="manual",
        )
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        request_id = submitted["id"]

        def roster_status():
            self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
            row = self.client.get(
                f"/api/v1/attendance/sessions/{self.session.id}/roster/"
            ).data["data"][0]
            return row

        row = roster_status()
        self.assertEqual(row["checked_in_status"], "absent")
        self.assertEqual(row["leave_status"], "pending_advisor_review")

        self.assertEqual(self.advisor_opinion(request_id).status_code, 200)
        self.assertEqual(roster_status()["leave_status"], "pending_program_head_review")

        self.assertEqual(self.program_head_opinion(request_id).status_code, 200)
        self.assertEqual(roster_status()["leave_status"], "pending_final_approval")

        self.assertEqual(
            self.final_decision(request_id, "approve", "อนุมัติ").status_code, 200
        )
        self.assertEqual(roster_status()["leave_status"], "approved")

        record = AttendanceRecord.objects.get(
            attendance_session=self.session, student=self.student
        )
        self.assertEqual(record.status, "absent")

    def test_returned_and_rejected_requests_are_visible_but_never_present(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        first = self.create_submitted()
        self.auth_user(self.advisor_user, "Str0ngTeach!Pass")
        self.assertEqual(
            self.client.post(
                f"/api/v1/leave-approvals/{first['id']}/return/",
                {"comment": "ขอแก้ไข"},
                format="json",
            ).status_code,
            200,
        )
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        row = self.client.get(
            f"/api/v1/attendance/sessions/{self.session.id}/roster/"
        ).data["data"][0]
        self.assertEqual(row["leave_status"], "returned")

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        second = self.create_submitted()
        self.advance_to_final_approval(second["id"])
        self.assertEqual(
            self.final_decision(second["id"], "reject", "ไม่ครบเงื่อนไข").status_code,
            200,
        )
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        row = self.client.get(
            f"/api/v1/attendance/sessions/{self.session.id}/roster/"
        ).data["data"][0]
        # The most recently submitted request is rejected.
        self.assertEqual(row["leave_status"], "rejected")
        self.assertEqual(row["leave_request_count"], 2)

    def test_course_review_works_while_request_is_pending(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.post(
            f"/api/v1/leave-courses/{submitted['courses'][0]['id']}/review/",
            {"review_status": "acknowledged", "comment": "รับทราบ"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        request = LeaveRequest.objects.get(pk=submitted["id"])
        # Course review must not advance the approval workflow.
        self.assertEqual(request.status, "pending_advisor_review")


class LeaveWorkflowPrintTests(LeaveTestBase):
    def test_print_includes_workflow_steps_and_history(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        self.assertEqual(self.advisor_opinion(submitted["id"]).status_code, 200)

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        printed = self.client.get(f"/api/v1/leave-requests/{submitted['id']}/print/")
        self.assertEqual(printed.status_code, 200, printed.data)
        document = printed.data["data"]
        self.assertEqual(len(document["workflow_steps"]), 3)
        self.assertEqual(
            document["workflow_steps"][0]["status_display"], "ดำเนินการแล้ว"
        )
        self.assertEqual(
            document["workflow_steps"][0]["comment"], "เห็นควรอนุญาต"
        )
        self.assertEqual(
            [entry["action"] for entry in document["workflow_history"]],
            ["submit", "advisor_opinion"],
        )
        self.assertEqual(document["status"], "pending_program_head_review")

