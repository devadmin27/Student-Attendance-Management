"""Class schedules — ตารางเรียน แยกออกจาก Attendance Session จริง (spec §9)."""
import uuid
from datetime import datetime, time, timedelta

from django.core.exceptions import ValidationError
from django.db import models


class ClassSchedule(models.Model):
    """กำหนดการเรียนประจำสัปดาห์ของรายวิชาที่เปิดสอน"""

    STATUS_CHOICES = (
        ("planned", "กำหนดการ"),
        ("active", "ใช้งานอยู่"),
        ("cancelled", "ยกเลิก"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_offering = models.ForeignKey(
        "courses.CourseOffering", on_delete=models.CASCADE, related_name="schedules",
        verbose_name="รายวิชาที่เปิดสอน",
    )
    weekday = models.PositiveSmallIntegerField(
        "วันเรียนวันที่", choices=[(i, d) for i, d in enumerate(
            ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"], start=0
        )]
    )
    start_time = models.TimeField("เวลาเริ่มต้น")
    end_time = models.TimeField("เวลาสิ้นสุด")
    classroom = models.CharField("ห้องเรียน", max_length=100, blank=True, default="")
    status = models.CharField("สถานะตารางเรียน", max_length=16, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "class_schedules"
        ordering = ["weekday", "start_time"]

    def clean(self):
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError("เวลาสิ้นสุดคาบเรียนต้องอยู่หลังเวลาเริ่มต้น")

    def __str__(self):
        return f"{self.course_offering} วัน{self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M}"
