"""RBAC tests: instructors must be able to READ academic/option data but not WRITE."""
from rest_framework import status

from apps.accounts.tests import BaseSamsTest


class OptionReadRBACTests(BaseSamsTest):
    def login_instructor(self):
        self.auth_user(self.instructor_user, "Str0ngTeach!Pass")

    def test_instructor_can_read_options(self):
        self.login_instructor()
        for path in [
            "/api/v1/academic-terms/",
            "/api/v1/class-groups/",
            "/api/v1/instructors/",
            "/api/v1/students/",
        ]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, status.HTTP_200_OK, path)

    def test_instructor_cannot_write_options(self):
        self.login_instructor()
        self.assertEqual(
            self.client.post("/api/v1/academic-terms/", {"academic_year": 2570, "semester": "1"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.post("/api/v1/class-groups/", {"group_code": "X", "group_name": "x"}).status_code,
            status.HTTP_403_FORBIDDEN,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/instructors/{self.instructor.pk}/").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_instructor_student_list_scoped_to_own_offerings(self):
        from apps.accounts.models import StudentProfile, User

        # นักศึกษากลุ่มอื่นที่ไม่ได้ลงทะเบียนรายวิชาของ instructor ต้องไม่ปรากฏ
        other_group_user = User.objects.create_user("s64009", "s9@x.ac.th", "Str0ngStud!Pass", role="student")
        other_student = other_group_user.student_profile
        other_student.student_code = "640009"
        other_student.save()
        self.login_instructor()
        rows = self.client.get("/api/v1/students/?page_size=100").json()["data"]
        self.assertIn("640001", [r["student_code"] for r in rows])  # enrolled in setUp
        self.assertNotIn("640009", [r["student_code"] for r in rows])  # unrelated
        # admin ยังเห็นครบทุกคน
        self.client.force_authenticate(self.admin_user)
        rows_all = self.client.get("/api/v1/students/?page_size=100").json()["data"]
        self.assertIn("640009", [r["student_code"] for r in rows_all])  # admin ยังเห็นครบ
