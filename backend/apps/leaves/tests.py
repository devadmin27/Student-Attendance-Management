"""Student leave Phase 1 tests (spec §10 Course Review + Attendance Integration)."""
from datetime import datetime, time, timedelta

from django.utils import timezone
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.tests import BaseSamsTest
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.audit.models import AuditLog
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.leaves.models import LeaveCourse, LeaveCourseReview, LeaveRequest
from apps.schedules.models import ClassSchedule


class LeaveTestBase(BaseSamsTest):
    """Base fixture plus a Monday-ish class 09:00–11:00 on the leave date."""

    def setUp(self):
        super().setUp()
        today = timezone.localdate()
        self.leave_date = today + timedelta(days=(7 - today.weekday()) % 7)
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
        self.assertEqual(request_data["status"], "submitted")
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
        self.assertEqual(leave_request.status, "submitted")
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
        self.assertEqual(row["leave_status"], "submitted")
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
        self.assertEqual(row["leave_status"], "submitted")

    def test_cancelled_or_draft_leave_is_not_shown(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        draft = self.create_draft().data["data"]
        row = self._roster()
        self.assertIsNone(row["leave_status"])

        self.auth_user(self.student_user, "Str0ngStud!Pass")
        submitted = self.create_submitted()
        row = self._roster()
        self.assertEqual(row["leave_status"], "submitted")

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
        self.assertEqual(row["leave_status"], "submitted")
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
        self.assertEqual(document["status_display"], "ส่งคำร้องแล้ว")
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
