"""Courses, course offerings per term, and enrollments."""
import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class Course(models.Model):
    """รายวิชา"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_code = models.CharField("รหัสรายวิชา", max_length=32, unique=True)
    course_name = models.CharField("ชื่อรายวิชา", max_length=200)
    credits = models.DecimalField(
        "หน่วยกิต", max_digits=3, decimal_places=1, default=1.0
    )
    description = models.TextField("รายละเอียด", blank=True, default="")
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "courses"
        ordering = ["course_code"]

    def __str__(self):
        return f"{self.course_code} — {self.course_name}"


class CourseOffering(models.Model):
    """การเปิดสอนรายวิชาในภาคการศึกษาหนึ่ง ๆ พร้อมอาจารย์ผู้รับผิดชอบและกลุ่มเรียน"""

    STATUS_CHOICES = (
        ("open", "เปิดรับลงทะเบียน"),
        ("in_progress", "กำลังเรียน"),
        ("completed", "จบภาคเรียนแล้ว"),
        ("cancelled", "ยกเลิก"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course, on_delete=models.PROTECT, related_name="offerings", verbose_name="รายวิชา"
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm", on_delete=models.PROTECT, related_name="offerings",
        verbose_name="ภาคการศึกษา",
    )
    instructor = models.ForeignKey(
        "accounts.InstructorProfile", on_delete=models.PROTECT, null=True, blank=True,
        related_name="offerings", verbose_name="อาจารย์หลัก",
        help_text="อาจารย์ผู้รับผิดชอบหลัก (ตั้งอัตโนมัติจากคนแรกในรายการ instructors)",
    )
    instructors = models.ManyToManyField(
        "accounts.InstructorProfile", blank=True,
        related_name="offerings_shared", verbose_name="อาจารย์ผู้รับผิดชอบ",
        help_text="รายการอาจารย์ผู้รับผิดชอบทั้งหมด — ทุกคนจัดการรายวิชานี้ได้ (คนแรกเป็นอาจารย์หลัก)",
    )
    class_group = models.ForeignKey(
        "academics.ClassGroup", on_delete=models.PROTECT, null=True, blank=True,
        related_name="offerings", verbose_name="กลุ่มเรียน",
    )
    status = models.CharField("สถานะ", max_length=16, choices=STATUS_CHOICES, default="open")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "course_offerings"
        ordering = ["-academic_term__academic_year", "course__course_code"]
        constraints = [
            # ป้องกันเปิดสอนรายวิชาเดียวกัน กลุ่มเดียวกัน ซ้ำในภาคเดียวกัน
            models.UniqueConstraint(
                fields=["course", "academic_term", "class_group"],
                condition=Q(class_group__isnull=False),
                name="uniq_offering_course_term_group",
            ),
        ]

    def __str__(self):
        group = f" ({self.class_group.group_code})" if self.class_group else ""
        return f"{self.course.course_code} {self.academic_term}{group}"

    def has_instructor(self, profile) -> bool:
        """True เมื่อ profile เป็นอาจารย์หลักหรืออาจารย์ร่วมของรายวิชานี้."""
        if profile is None:
            return False
        if self.instructor_id == profile.id:
            return True
        return self.instructors.filter(pk=profile.pk).exists()


class Enrollment(models.Model):
    """การลงทะเบียนเรียนของนักศึกษาในรายวิชาที่เปิดสอน"""

    STATUS_CHOICES = (
        ("enrolled", "กำลังศึกษา"),
        ("dropped", "ถอนรายวิชา"),
        ("completed", "จบรายวิชา"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE,
        related_name="enrollments", verbose_name="นักศึกษา",
    )
    course_offering = models.ForeignKey(
        CourseOffering, on_delete=models.PROTECT, related_name="enrollments",
        verbose_name="รายวิชาที่เปิดสอน",
    )
    enrollment_status = models.CharField(
        "สถานะการลงทะเบียน", max_length=16, choices=STATUS_CHOICES, default="enrolled"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "enrollments"
        ordering = ["course_offering__course__course_code", "student__student_code"]
        constraints = [
            # ห้ามลงทะเบียนรายวิชาเดียวกันซ้ำในภาคการศึกษาเดียวกัน (spec §8.2)
            models.UniqueConstraint(
                fields=["student", "course_offering"], name="uniq_enrollment_once"
            ),
        ]
        indexes = [
            models.Index(fields=["student", "enrollment_status"]),
            models.Index(fields=["course_offering", "enrollment_status"]),
        ]

    def clean(self):
        if self.course_offering.status == "cancelled":
            raise ValidationError("ไม่สามารถลงทะเบียนรายวิชาที่ถูกยกเลิกได้")

    def __str__(self):
        return f"{self.student.student_code} → {self.course_offering}"
