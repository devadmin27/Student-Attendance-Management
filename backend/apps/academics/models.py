"""Academic structure: programs, class groups, thai academic terms."""
import uuid

from django.core.exceptions import ValidationError
from django.db import models


class Program(models.Model):
    """หลักสูตร"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    program_code = models.CharField("รหัสหลักสูตร", max_length=32, unique=True)
    program_name = models.CharField("ชื่อหลักสูตร", max_length=200)
    degree_level = models.CharField(
        "ระดับการศึกษา", max_length=50,
        choices=[("bachelor", "ปริญญาตรี"), ("master", "ปริญญาโท"), ("doctoral", "ปริญญาเอก")],
        default="bachelor",
    )
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "programs"
        ordering = ["program_code"]

    def __str__(self):
        return f"{self.program_code} — {self.program_name}"


class ClassGroup(models.Model):
    """ห้องเรียน / กลุ่มเรียน"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group_code = models.CharField("รหัสกลุ่ม", max_length=32, unique=True)
    group_name = models.CharField("ชื่อกลุ่มเรียน", max_length=100)
    program = models.ForeignKey(
        Program, on_delete=models.CASCADE, related_name="class_groups", verbose_name="หลักสูตร"
    )
    academic_year_level = models.PositiveSmallIntegerField("ชั้นปี", default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "class_groups"
        ordering = ["group_code"]

    def __str__(self):
        return self.group_name


class AcademicTerm(models.Model):
    """ภาคการศึกษา (ปีการศึกษาไทยเก็บเป็นชุดข้อมูลตามกติกาที่กำหนด"""

    SEMESTER_CHOICES = (
        ("1", "ภาคเรียนที่ 1"),
        ("2", "ภาคเรียนที่ 2"),
        ("3", "ภาคเรียนฤดูร้อน"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    academic_year = models.PositiveIntegerField(
        "ปีการศึกษา (พ.ศ.)",
        help_text="ปีการศึกษาไทย พ.ศ. เช่น 2569 — เก็บตามที่ป้อน ไม่แปลงอัตโนมัติ",
    )
    semester = models.CharField("ภาคการศึกษา", max_length=2, choices=SEMESTER_CHOICES)
    start_date = models.DateField("วันเริ่มต้น")
    end_date = models.DateField("วันสิ้นสุด")
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    is_current = models.BooleanField(
        "ภาคปัจจุบัน", default=False,
        help_text="อนุญาตให้มีได้เพียงภาคเดียวต่อการใช้งาน (ผ่าน application-level ตรวจสอบ)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "academic_terms"
        ordering = ["-academic_year", "semester"]
        constraints = [
            models.UniqueConstraint(
                fields=["academic_year", "semester"], name="uniq_term_year_semester"
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="term_end_after_start",
            ),
        ]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("วันสิ้นสุดภาคการศึกษาต้องไม่ก่อนวันเริ่มต้น")

    def __str__(self):
        return f"{self.academic_year}/{self.semester}"
