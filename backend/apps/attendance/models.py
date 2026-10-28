"""Attendance sessions, QR tokens, attendance records (spec §9, §10, §12)."""
import uuid

from django.conf import settings as dj_settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class AttendanceSession(models.Model):
    """คาบเรียนที่มีการเปิดเช็คชื่อจริง (แยกจากตารางเรียน)"""

    STATUS_CHOICES = (
        ("scheduled", "กำหนดการ"),
        ("open", "เปิดรับเช็คชื่อ"),
        ("paused", "หยุดชั่วคราว"),
        ("closed", "ปิดแล้ว"),
        ("cancelled", "ยกเลิก"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course_offering = models.ForeignKey(
        "courses.CourseOffering", on_delete=models.PROTECT, related_name="attendance_sessions",
        verbose_name="รายวิชาที่เปิดสอน",
    )
    class_schedule = models.ForeignKey(
        "schedules.ClassSchedule", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="attendance_sessions", verbose_name="ตารางเรียนที่เชื่อมโยง",
    )
    instructor = models.ForeignKey(
        "accounts.InstructorProfile", on_delete=models.PROTECT, related_name="attendance_sessions",
        verbose_name="อาจารย์ผู้เปิดคาบ",
    )
    session_date = models.DateField("วันที่เรียน")
    check_in_start = models.DateTimeField("เวลาเริ่มรับเช็คชื่อ")
    check_in_end = models.DateTimeField("เวลาปิดรับเช็คชื่อ")
    late_threshold_minutes = models.PositiveSmallIntegerField(
        "เกณฑ์นับมาสาย (นาที)", default=15
    )
    status = models.CharField(
        "สถานะ Session", max_length=16, choices=STATUS_CHOICES, default="scheduled"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField("เวลาปิดคาบ", null=True, blank=True)

    class Meta:
        db_table = "attendance_sessions"
        ordering = ["-session_date", "-created_at"]
        indexes = [
            models.Index(fields=["course_offering", "session_date"]),
            models.Index(fields=["status", "session_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(check_in_end__gte=models.F("check_in_start")),
                name="session_end_not_before_start",
            ),
        ]

    def clean(self):
        if self.check_in_end and self.check_in_start and self.check_in_end < self.check_in_start:
            raise ValidationError("เวลาปิดรับเช็คชื่อต้องไม่ก่อนเวลาเริ่ม")

    @property
    def enrolled_count(self) -> int:
        return self.course_offering.enrollments.filter(
            enrollment_status="enrolled"
        ).count()

    @property
    def checked_in_count(self) -> int:
        return self.records.count()

    def is_checkin_open_at(self, now=None) -> bool:
        """สภาพ session ที่ยังรับเช็คชื่อได้: open + อยู่ในหน้าต่างเวลา.

        หน้าต่าง = [check_in_start, check_in_end + late_threshold + grace]
        เช็คก่อน check_in_end = present, หลัง = late, หลังหน้าต่าง = ปิด.
        """
        now = now or timezone.now()
        if self.status != "open":
            return False
        if self.check_in_start and now < self.check_in_start:
            return False
        latest = None
        if self.check_in_end:
            latest = self.check_in_end + timezone.timedelta(
                minutes=int(self.late_threshold_minutes or 0)
            )
            latest = latest + timezone.timedelta(seconds=dj_settings.CHECKIN_GRACE_SECONDS)
        return latest is None or now <= latest

    def __str__(self):
        return f"{self.course_offering} — {self.session_date} ({self.status})"


class QRToken(models.Model):
    """QR token ของ Session — เก็บเฉพาะ SHA-256 hash ไม่เก็บ token ตัวเต็ม.

    โมเดลความปลอดภัย (spec §10.2):
    - Token เป็นค่าสุ่มจาก secrets.token_urlsafe คาดเดายาก
    - ใช้ร่วมกันได้ทั้งคาบ (แบ่ง label "session token") แต่แต่ละนักศึกษาสร้าง
      Attendance Record ได้หนึ่งรายการต่อ Session (constraint ใน AttendanceRecord)
    - หมดอายุตาม TTL สั้น และ mark หมดอายุเมื่อ Session ปิด
    - รับการ rotate ทุก TTL เพื่อป้องกันการถ่ายภาพ QR ต่อไปยังผู้อื่น
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance_session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="qr_tokens",
        verbose_name="คาบเรียน",
    )
    token_hash = models.CharField(  # sha256 hex
        "รหัสแฮชของ Token", max_length=64, unique=True
    )
    issued_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="issued_qr_tokens",
        null=True, verbose_name="ผู้ออกโทเคน",
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField("หมดอายุเมื่อ")
    revoked_at = models.DateTimeField("เพิกถอนเมื่อ", null=True, blank=True)
    use_count = models.PositiveIntegerField("จำนวนการใช้เช็คชื่อสำเร็จ", default=0)

    class Meta:
        db_table = "qr_tokens"
        ordering = ["-issued_at"]
        indexes = [
            models.Index(fields=["attendance_session", "token_hash"]),
            models.Index(fields=["expires_at", "revoked_at"]),
        ]

    @property
    def is_valid_now(self) -> bool:
        now = timezone.now()
        return (
            self.revoked_at is None
            and now >= self.issued_at  # defensive; auto_now_add sets this
            and now < self.expires_at
        )


class AttendanceRecord(models.Model):
    """บันทึกการเข้าเรียนรายบุคคลต่อคาบ — UNIQUE(session, student) ตาม spec §10.4"""

    STATUS_CHOICES = (
        ("present", "เข้าเรียน"),
        ("late", "มาสาย"),
        ("absent", "ขาดเรียน"),
        ("excused", "ลา/ได้รับอนุญาต"),
    )

    METHOD_CHOICES = (
        ("qr", "QR Code"),
        ("manual", "บันทึกโดยอาจารย์"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    attendance_session = models.ForeignKey(
        AttendanceSession, on_delete=models.CASCADE, related_name="records",
        verbose_name="คาบเรียน",
    )
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE, related_name="attendance_records",
        verbose_name="นักศึกษา",
    )
    status = models.CharField(
        "สถานะ", max_length=16, choices=STATUS_CHOICES, default="present"
    )
    checked_in_at = models.DateTimeField("เวลาที่เช็คชื่อ", auto_now_add=True)
    check_in_method = models.CharField(
        "วิธีการเช็คชื่อ", max_length=16, choices=METHOD_CHOICES, default="qr"
    )
    qr_token = models.ForeignKey(
        QRToken, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="records", verbose_name="โทเคนที่ใช้",
    )
    edited_by = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, null=True, blank=True,
        related_name="edited_attendance_records", verbose_name="ผู้แก้ไขล่าสุด",
    )
    edit_reason = models.TextField("เหตุผลการแก้ไข", blank=True, default="")
    source_metadata = models.JSONField("ข้อมูลอ้างอิงแหล่งที่มา", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "attendance_records"
        ordering = ["-checked_in_at"]
        indexes = [
            models.Index(fields=["attendance_session", "status"]),
            models.Index(fields=["student", "status"]),
        ]
        constraints = [
            # ไม่มี Attendance Record ของนักศึกษาซ้ำใน Session เดียวกัน (spec §10.4)
            models.UniqueConstraint(
                fields=["attendance_session", "student"],
                name="uniq_attendance_per_session_student",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["present", "late", "absent", "excused"]),
                name="attendance_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.attendance_session_id} {self.student.student_code} {self.status}"
