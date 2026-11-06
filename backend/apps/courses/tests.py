"""Course offering (multi-instructor) + enrollment bulk + RBAC scope tests."""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from apps.accounts.models import StudentProfile, User
from apps.accounts.tests import BaseSamsTest
from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.courses.models import CourseOffering, Enrollment


class MultiInstructorOfferingTests(BaseSamsTest):
    def login_instructor(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_admin_sets_multiple_instructors_primary_syncs_to_first(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        other = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        second = other.instructor_profile
        response = self.client.post(
            "/api/v1/course-offerings/",
            {"course": str(self.course.pk), "academic_term": str(self.term.pk),
             "instructors": [str(self.instructor.pk), str(second.pk)]},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        payload = response.json()["data"]
        offering = CourseOffering.objects.get(pk=payload["id"])
        self.assertEqual(offering.instructor, self.instructor)  # first = primary
        self.assertEqual(set(offering.instructors.all()), {self.instructor, second})
        self.assertEqual(len(payload["instructor_names"]), 2)

    def test_update_removing_primary_reassigns_to_first_remaining(self):
        other = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        second = other.instructor_profile
        self.offering.instructors.add(self.instructor, second)
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.patch(
            f"/api/v1/course-offerings/{self.offering.pk}/",
            {"instructors": [str(second.pk)]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.offering.refresh_from_db()
        self.assertEqual(self.offering.instructor, second)
        self.assertEqual(list(self.offering.instructors.all()), [second])

    def test_co_instructor_sees_offering_and_can_create_session(self):
        other = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        second = other.instructor_profile
        self.offering.instructors.add(second)  # co-instructor, not primary
        self.auth_user(other, "Str0ngTeach!Pass")
        listing = self.client.get("/api/v1/course-offerings/").json()["data"]
        self.assertIn(str(self.offering.pk), [str(r["id"]) for r in listing])
        now = timezone.now()
        response = self.client.post(
            "/api/v1/attendance/sessions/",
            {"course_offering": str(self.offering.pk),
             "session_date": (now + timedelta(days=1)).date().isoformat(),
             "check_in_start": (now + timedelta(days=1, hours=1)).isoformat(),
             "check_in_end": (now + timedelta(days=1, hours=2)).isoformat()},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)


class OfferingDeleteTests(BaseSamsTest):
    """อาจารย์ลบการเปิดสอนของตนได้; ของคนอื่นไม่ได้; ที่มีข้อมูลผูกจะถูกยกเลิกแทน"""

    def login_instructor(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_instructor_deletes_own_empty_offering(self):
        self.login_instructor()
        # offering ที่ไม่มีข้อมูลลูก (BaseSamsTest ผูก enrollment กับ self.offering)
        empty = CourseOffering.objects.create(
            course=self.course, academic_term=self.term, instructor=self.instructor,
        )
        response = self.client.delete(f"/api/v1/course-offerings/{empty.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(CourseOffering.objects.filter(pk=empty.pk).exists())

    def test_instructor_delete_offering_with_enrollment_soft_deletes(self):
        self.login_instructor()
        response = self.client.delete(f"/api/v1/course-offerings/{self.offering.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, getattr(response, "data", None))
        self.offering.refresh_from_db()
        self.assertEqual(self.offering.status, "cancelled")
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_instructor_cannot_delete_other_teachers_offering(self):
        other = User.objects.create_user(
            "teacher9", "t9@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        foreign = CourseOffering.objects.create(
            course=self.course, academic_term=self.term, instructor=other.instructor_profile,
        )
        self.login_instructor()
        response = self.client.delete(f"/api/v1/course-offerings/{foreign.pk}/")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertTrue(CourseOffering.objects.filter(pk=foreign.pk).exists())


class EnrollmentRBACTests(BaseSamsTest):
    def login_instructor(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_bulk_enroll_creates_active_group_students_and_skips_duplicates(self):
        extra_user = User.objects.create_user("s64002", "s2@x.ac.th", "Str0ngStud!Pass", role="student")
        extra = extra_user.student_profile
        extra.student_code = "640002"
        extra.first_name = "เพิ่ม"
        extra.last_name = "ทดสอบ"
        extra.program = self.program
        extra.class_group = self.group
        extra.save()
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.post(
            "/api/v1/enrollments/bulk/",
            {"course_offering": str(self.offering.pk), "class_group": str(self.group.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        # student 1 มีอยู่ก่อน (setUp) → created=1 (extra), skipped=1
        self.assertEqual(response.data["data"]["created"], 1)
        self.assertEqual(response.data["data"]["skipped"], 1)

    def test_bulk_enroll_reports_dropped_without_reinstating(self):
        self.enrollment.enrollment_status = "dropped"
        self.enrollment.save(update_fields=["enrollment_status"])
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.post(
            "/api/v1/enrollments/bulk/",
            {"course_offering": str(self.offering.pk), "class_group": str(self.group.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data["data"]
        self.assertEqual((data["created"], data["skipped"], data["dropped"]), (0, 0, 1))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "dropped")

    def test_bulk_enroll_blocked_for_completed_offering(self):
        self.offering.status = "completed"
        self.offering.save(update_fields=["status"])
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.post(
            "/api/v1/enrollments/bulk/",
            {"course_offering": str(self.offering.pk), "class_group": str(self.group.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["code"], "OFFERING_CLOSED")

    def test_instructor_cannot_bulk_enroll_into_other_teacher_offering(self):
        other_user = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        other_offering = CourseOffering.objects.create(
            course=self.course, academic_term=self.term,
            instructor=other_user.instructor_profile,
        )
        self.login_instructor()
        response = self.client.post(
            "/api/v1/enrollments/bulk/",
            {"course_offering": str(other_offering.pk), "class_group": str(self.group.pk)},
        )
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        self.assertFalse(response.data["success"])

    def test_instructor_can_bulk_enroll_own_offering(self):
        self.login_instructor()
        response = self.client.post(
            "/api/v1/enrollments/bulk/",
            {"course_offering": str(self.offering.pk), "class_group": str(self.group.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["data"]["skipped"], 1)  # setUp student
        self.assertEqual(Enrollment.objects.filter(course_offering=self.offering).count(), 1)

    def test_schedule_create_guard_for_other_teacher_offering(self):
        other_user = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        other_offering = CourseOffering.objects.create(
            course=self.course, academic_term=self.term,
            instructor=other_user.instructor_profile,
        )
        self.login_instructor()
        response = self.client.post(
            "/api/v1/class-schedules/",
            {"course_offering": str(other_offering.pk), "weekday": "1",
             "start_time": "09:00", "end_time": "11:00"},
        )
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))


class EnrollmentLifecycleTests(BaseSamsTest):
    """ถอน = เก็บประวัติ; ลบ = เฉพาะเมื่อยังไม่มีประวัติเช็คชื่อ."""

    def login_admin(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")

    def add_attendance(self):
        now = timezone.now()
        session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=now - timedelta(minutes=5),
            check_in_end=now + timedelta(minutes=5),
        )
        return AttendanceRecord.objects.create(
            attendance_session=session, student=self.student, status="present",
        )

    def new_student(self, code):
        user = User.objects.create_user(f"s{code}", f"{code}@x.ac.th", "Str0ngStud!Pass", role="student")
        profile = user.student_profile
        profile.student_code = code
        profile.first_name = "ทดสอบ"
        profile.last_name = code
        profile.program = self.program
        profile.class_group = self.group
        profile.save()
        return profile

    def test_withdraw_keeps_attendance_history(self):
        record = self.add_attendance()
        self.login_admin()
        response = self.client.post(
            f"/api/v1/enrollments/{self.enrollment.pk}/withdraw/",
            {"reason": "ลงทะเบียนผิดกลุ่ม"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "dropped")
        self.assertTrue(AttendanceRecord.objects.filter(pk=record.pk).exists())

        listing = self.client.get("/api/v1/enrollments/").data["data"]
        row = next(r for r in listing if r["id"] == str(self.enrollment.pk))
        self.assertEqual(row["attendance_record_count"], 1)

    def test_delete_enrollment_with_attendance_is_blocked(self):
        self.add_attendance()
        self.login_admin()
        response = self.client.delete(f"/api/v1/enrollments/{self.enrollment.pk}/")
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT, response.data)
        self.assertEqual(response.data["code"], "HAS_ATTENDANCE")
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_delete_enrollment_without_attendance_succeeds(self):
        self.login_admin()
        response = self.client.delete(f"/api/v1/enrollments/{self.enrollment.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_reinstate_dropped_enrollment(self):
        self.enrollment.enrollment_status = "dropped"
        self.enrollment.save(update_fields=["enrollment_status"])
        self.login_admin()
        response = self.client.post(f"/api/v1/enrollments/{self.enrollment.pk}/reinstate/")
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "enrolled")

    def test_cannot_enroll_into_completed_offering(self):
        self.offering.status = "completed"
        self.offering.save(update_fields=["status"])
        student = self.new_student("649999")
        self.login_admin()
        response = self.client.post(
            "/api/v1/enrollments/",
            {"student": str(student.pk), "course_offering": str(self.offering.pk)},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_cannot_reinstate_into_completed_offering(self):
        self.enrollment.enrollment_status = "dropped"
        self.enrollment.save(update_fields=["enrollment_status"])
        self.offering.status = "completed"
        self.offering.save(update_fields=["status"])
        self.login_admin()
        response = self.client.post(f"/api/v1/enrollments/{self.enrollment.pk}/reinstate/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["code"], "OFFERING_CLOSED")

    def test_edit_cannot_reinstate_into_completed_offering(self):
        self.enrollment.enrollment_status = "dropped"
        self.enrollment.save(update_fields=["enrollment_status"])
        self.offering.status = "completed"
        self.offering.save(update_fields=["status"])
        self.login_admin()
        response = self.client.patch(
            f"/api/v1/enrollments/{self.enrollment.pk}/",
            {"enrollment_status": "enrolled"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "dropped")

    def test_cannot_change_student_when_attendance_exists(self):
        self.add_attendance()
        student = self.new_student("649998")
        self.login_admin()
        response = self.client.patch(
            f"/api/v1/enrollments/{self.enrollment.pk}/",
            {"student": str(student.pk)},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

    def test_instructor_cannot_withdraw_other_teachers_enrollment(self):
        other_user = User.objects.create_user(
            "teacher8", "t8@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        foreign_offering = CourseOffering.objects.create(
            course=self.course, academic_term=self.term,
            instructor=other_user.instructor_profile,
        )
        foreign = Enrollment.objects.create(
            student=self.new_student("649997"), course_offering=foreign_offering,
        )
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.client.post(f"/api/v1/enrollments/{foreign.pk}/withdraw/")
        self.assertIn(response.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND))
        foreign.refresh_from_db()
        self.assertEqual(foreign.enrollment_status, "enrolled")

    def test_term_filter_accepts_uuid_and_ignores_invalid_value(self):
        self.login_admin()
        ok = self.client.get("/api/v1/enrollments/", {"academic_term": str(self.term.pk)})
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertIn(
            str(self.enrollment.pk), [str(r["id"]) for r in ok.data["data"]]
        )
        bad = self.client.get("/api/v1/enrollments/", {"academic_term": "not-a-uuid"})
        self.assertEqual(bad.status_code, status.HTTP_200_OK)
        self.assertEqual(bad.data["data"], [])


class EnrollmentBatchTests(BaseSamsTest):
    """Batch withdraw/delete must process each row independently."""

    def login_admin(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")

    def new_student(self, code):
        user = User.objects.create_user(
            f"s{code}", f"{code}@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        profile = user.student_profile
        profile.student_code = code
        profile.first_name = "ทดสอบ"
        profile.last_name = code
        profile.program = self.program
        profile.class_group = self.group
        profile.save()
        return profile

    def new_enrollment(self, code):
        return Enrollment.objects.create(
            student=self.new_student(code), course_offering=self.offering
        )

    def add_attendance(self, student):
        now = timezone.now()
        session = AttendanceSession.objects.create(
            course_offering=self.offering,
            instructor=self.instructor,
            session_date=timezone.localdate(),
            check_in_start=now - timedelta(minutes=5),
            check_in_end=now + timedelta(minutes=5),
        )
        return AttendanceRecord.objects.create(
            attendance_session=session, student=student, status="present",
        )

    def post_batch(self, path, ids, **extra):
        return self.client.post(
            path, {"ids": [str(i) for i in ids], **extra},
            content_type="application/json",
        )

    def test_batch_withdraw_keeps_history_and_reports_skipped(self):
        second = self.new_enrollment("B10002")
        second.enrollment_status = "dropped"
        second.save(update_fields=["enrollment_status"])
        record = self.add_attendance(self.student)
        self.login_admin()
        response = self.post_batch(
            "/api/v1/enrollments/batch-withdraw/",
            [self.enrollment.pk, second.pk],
            reason="ลงทะเบียนผิดกลุ่ม",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data["data"]
        self.assertEqual((data["succeeded"], data["skipped"], data["failed"]), (1, 1, 0))
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "dropped")
        self.assertTrue(AttendanceRecord.objects.filter(pk=record.pk).exists())

    def test_batch_withdraw_requires_reason(self):
        self.login_admin()
        response = self.post_batch(
            "/api/v1/enrollments/batch-withdraw/", [self.enrollment.pk]
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
        self.assertEqual(response.data["code"], "REASON_REQUIRED")
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "enrolled")

    def test_batch_withdraw_reports_completed_rows_as_failed(self):
        second = self.new_enrollment("B10003")
        self.enrollment.enrollment_status = "completed"
        self.enrollment.save(update_fields=["enrollment_status"])
        self.login_admin()
        response = self.post_batch(
            "/api/v1/enrollments/batch-withdraw/",
            [self.enrollment.pk, second.pk],
            reason="ทดสอบบางแถวถอนไม่ได้",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data["data"]
        self.assertEqual((data["succeeded"], data["failed"]), (1, 1))
        self.enrollment.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(self.enrollment.enrollment_status, "completed")
        self.assertEqual(second.enrollment_status, "dropped")
        failed = next(r for r in data["results"] if not r["ok"])
        self.assertEqual(failed["code"], "INVALID_STATUS")

    def test_batch_delete_mixed_history(self):
        second = self.new_enrollment("B10004")
        self.add_attendance(self.student)
        self.login_admin()
        response = self.post_batch(
            "/api/v1/enrollments/batch-delete/",
            [self.enrollment.pk, second.pk],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data["data"]
        self.assertEqual((data["succeeded"], data["failed"]), (1, 1))
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())
        self.assertFalse(Enrollment.objects.filter(pk=second.pk).exists())
        failed = next(r for r in data["results"] if not r["ok"])
        self.assertEqual(failed["code"], "HAS_ATTENDANCE")

    def test_batch_delete_instructor_cannot_touch_other_teacher_rows(self):
        other_user = User.objects.create_user(
            "teacher9", "t9@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        foreign_offering = CourseOffering.objects.create(
            course=self.course, academic_term=self.term,
            instructor=other_user.instructor_profile,
        )
        foreign = Enrollment.objects.create(
            student=self.new_student("B10005"), course_offering=foreign_offering,
        )
        own = self.new_enrollment("B10006")
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        response = self.post_batch(
            "/api/v1/enrollments/batch-delete/",
            [own.pk, foreign.pk],
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        data = response.data["data"]
        self.assertEqual((data["succeeded"], data["failed"]), (1, 1))
        self.assertFalse(Enrollment.objects.filter(pk=own.pk).exists())
        self.assertTrue(Enrollment.objects.filter(pk=foreign.pk).exists())
        failed = next(r for r in data["results"] if not r["ok"])
        self.assertEqual(failed["code"], "NOT_FOUND")

    def test_batch_rejects_empty_and_invalid_ids(self):
        self.login_admin()
        empty = self.client.post(
            "/api/v1/enrollments/batch-delete/", {"ids": []},
            content_type="application/json",
        )
        self.assertEqual(empty.status_code, status.HTTP_400_BAD_REQUEST, empty.data)
        self.assertEqual(empty.data["code"], "INVALID_IDS")

        invalid = self.client.post(
            "/api/v1/enrollments/batch-delete/", {"ids": ["not-a-uuid"]},
            content_type="application/json",
        )
        self.assertEqual(invalid.status_code, status.HTTP_400_BAD_REQUEST, invalid.data)
        self.assertEqual(invalid.data["code"], "INVALID_IDS")
