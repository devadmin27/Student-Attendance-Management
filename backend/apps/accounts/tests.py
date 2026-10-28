"""Auth + RBAC + user management tests (spec §17.1)."""
import uuid
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import StudentProfile, User
from apps.academics.models import AcademicTerm, ClassGroup, Program
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.attendance.models import AttendanceRecord, AttendanceSession


class BaseSamsTest(APITestCase):
    maxDiff = None

    @classmethod
    def setUpTestData(cls):
        cls.program = Program.objects.create(
            program_code="CSE", program_name="วิศวกรรมคอมพิวเตอร์"
        )
        cls.group = ClassGroup.objects.create(
            group_code="CSE-1", group_name="ห้อง 1", program=cls.program,
            academic_year_level=1,
        )
        cls.term = AcademicTerm.objects.create(
            academic_year=2569, semester="1",
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=90),
        )
        cls.admin_user = User.objects.create_user(
            "admin1", "admin1@x.ac.th", "Str0ngAdmin!Pass", role="admin",
            is_staff=True, is_superuser=True,
        )
        cls.instructor_user = User.objects.create_user(
            "teacher1", "t1@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        cls.instructor = cls.instructor_user.instructor_profile
        cls.instructor.first_name = "สมสอน"
        cls.instructor.last_name = "ทดสอบ"
        cls.instructor.save()
        cls.student_user = User.objects.create_user(
            "s64001", "s1@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        cls.student = cls.student_user.student_profile
        cls.student.student_code = "640001"
        cls.student.first_name = "นักเรียน"
        cls.student.last_name = "ทดสอบ"
        cls.student.program = cls.program
        cls.student.class_group = cls.group
        cls.student.academic_year_level = 1
        cls.student.save()
        cls.course = Course.objects.create(course_code="IN20-111", course_name="ทดสอบรายวิชา")
        cls.offering = CourseOffering.objects.create(
            course=cls.course, academic_term=cls.term, instructor=cls.instructor,
            class_group=cls.group,
        )
        cls.enrollment = Enrollment.objects.create(
            student=cls.student, course_offering=cls.offering
        )

    def auth_user(self, user, password):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": user.username, "password": password},
        )
        token = response.data["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return token

    def setUp(self):
        # Reset throttle history (LocMem cache is shared across tests).
        from django.core.cache import cache

        cache.clear()


class LoginTests(BaseSamsTest):
    def test_login_success_returns_role_and_access(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"username": "s64001", "password": "Str0ngStud!Pass"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        self.assertIn("access", response.data["data"])
        self.assertEqual(response.data["data"]["user"]["role"], "student")
        self.assertEqual(response.data["data"]["user"]["profile"]["student_code"], "640001")
        # HttpOnly refresh cookie must be set (no refresh in body for clients)
        self.assertIn("sams_refresh", response.cookies)
        cookie = response.cookies["sams_refresh"]
        self.assertEqual(cookie["httponly"], True)
        self.assertEqual(cookie["samesite"], "Lax")

    def test_login_wrong_password_is_rejected(self):
        response = self.client.post(
            "/api/v1/auth/login/", {"username": "s64001", "password": "wrong"}
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(response.data["success"])

    def test_login_message_does_not_disclose_existing_account(self):
        """Unknown username vs wrong password must be identical."""
        r1 = self.client.post(
            "/api/v1/auth/login/", {"username": "s64001", "password": "bad"}
        )
        r2 = self.client.post(
            "/api/v1/auth/login/", {"username": "nobody", "password": "bad"}
        )
        self.assertEqual(r1.data["code"], r2.data["code"])
        self.assertNotIn("nobody", r2.data["message"])

    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class RefreshLogoutTests(BaseSamsTest):
    login_user = None

    def _login(self, user, password):
        response = self.client.post(
            "/api/v1/auth/login/", {"username": user.username, "password": password}
        )
        return response

    def test_refresh_via_cookie_rotates_and_reuse_is_blocked(self):
        response = self._login(self.student_user, "Str0ngStud!Pass")
        raw_refresh = response.cookies["sams_refresh"].value
        self.client.credentials()
        # First refresh succeeds and rotates the token
        first = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(first.status_code, 200)
        new_access = first.data["data"]["access"]
        self.assertTrue(new_access)
        rotated = first.cookies["sams_refresh"].value
        # Reusing the ORIGINAL cookie token is rejected (blacklisted)
        self.client.cookies["sams_refresh"] = raw_refresh
        reuse = self.client.post("/api/v1/auth/refresh/")
        # Rotation already consumed it; this simulates token reuse detection
        self.assertIn(reuse.status_code, (401, 400))
        self.assertFalse(reuse.data["success"])
        # New refresh token works once more
        self.client.cookies["sams_refresh"] = rotated
        second = self.client.post("/api/v1/auth/refresh/")
        self.assertEqual(second.status_code, 200)

    def test_logout_revokes_refresh(self):
        response = self._login(self.student_user, "Str0ngStud!Pass")
        access = response.data["data"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        logout = self.client.post("/api/v1/auth/logout/")
        self.assertEqual(logout.status_code, 200)
        self.client.credentials(HTTP_AUTHORIZATION="")
        refreshed = self.client.post(
            "/api/v1/auth/refresh/",
            data={},
            HTTP_COOKIE=f"sams_refresh={response.cookies['sams_refresh'].value}",
        )
        self.assertEqual(refreshed.status_code, 401)


class RBACTests(BaseSamsTest):
    def test_anonymous_is_401_on_protected_endpoints(self):
        for url in [
            "/api/v1/users/", "/api/v1/students/", "/api/v1/courses/",
            "/api/v1/dashboard/admin/", "/api/v1/attendance/sessions/",
        ]:
            self.assertEqual(
                self.client.get(url).status_code, status.HTTP_401_UNAUTHORIZED, url
            )

    def test_student_cannot_access_admin_endpoints(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        for url in [
            "/api/v1/users/", "/api/v1/students/", "/api/v1/instructors/",
            "/api/v1/dashboard/admin/", "/api/v1/audit-logs/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, url)
            self.assertEqual(response.data["code"], "PERMISSION_DENIED")

    def test_student_cannot_create_users(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.post(
            "/api/v1/users/",
            {"username": "hacked", "password": "whatever", "role": "admin"},
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(User.objects.filter(username="hacked").exists())

    def test_instructor_cannot_see_other_instructors_offerings(self):
        other_teacher = User.objects.create_user(
            "teacher2", "t2@x.ac.th", "Str0ngTeach!Pass", role="instructor"
        )
        other = other_teacher.instructor_profile
        other.first_name = "คนอื่น"
        other.save()
        other_offering = CourseOffering.objects.create(
            course=self.course, academic_term=self.term, instructor=other,
        )
        other_student_user = User.objects.create_user(
            "s64002", "s2@x.ac.th", "Str0ngStud!Pass", role="student"
        )
        other_student = other_student_user.student_profile
        other_student.student_code = "640002"
        other_student.first_name = "คนอื่น"
        other_student.last_name = "นักเรียน"
        other_student.program = self.program
        other_student.save()
        Enrollment.objects.create(student=other_student, course_offering=other_offering)
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        listing = self.client.get("/api/v1/course-offerings/").json()
        offered_ids = [row["id"] for row in listing["data"]]
        self.assertNotIn(str(other_offering.pk), offered_ids)
        # Direct IDOR on the ID itself must still be denied
        detail = self.client.get(f"/api/v1/course-offerings/{other_offering.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

    def test_role_cannot_be_changed_by_non_admin(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")
        me_id = str(self.instructor_user.pk)
        response = self.client.patch(
            f"/api/v1/users/{me_id}/", {"role": "admin"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.instructor_user.refresh_from_db()
        self.assertEqual(self.instructor_user.role, "instructor")

    def test_user_create_validates_password(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.post(
            "/api/v1/users/",
            {"username": "weakguy", "password": "12345678", "role": "student"},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertFalse(User.objects.filter(username="weakguy").exists())


class DashboardTests(BaseSamsTest):
    def test_admin_dashboard_real_numbers(self):
        self.auth_user(self.admin_user, "Str0ngAdmin!Pass")
        response = self.client.get("/api/v1/dashboard/admin/")
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["users_total"], User.objects.count())
        self.assertEqual(data["students_total"], StudentProfile.objects.count())
        self.assertEqual(data["instructors_total"], 1)
        self.assertEqual(data["courses_total"], 1)

    def test_student_dashboard_scope(self):
        self.auth_user(self.student_user, "Str0ngStud!Pass")
        response = self.client.get("/api/v1/dashboard/student/")
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]
        self.assertEqual(data["profile"]["student_code"], "640001")
        self.assertIn(
            str(self.offering.pk), [row["id"] for row in data["courses"]]
        )

    def test_healthcheck_reports_db(self):
        response = self.client.get("/api/v1/health/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["database"], "connected")
