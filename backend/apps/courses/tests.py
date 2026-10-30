"""Course offering (multi-instructor) + enrollment bulk + RBAC scope tests."""
from datetime import timedelta

from django.utils import timezone
from rest_framework import status

from apps.accounts.models import StudentProfile, User
from apps.accounts.tests import BaseSamsTest
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
