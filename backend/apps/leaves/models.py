"""Student leave requests, course-specific reviews, and future role assignments.

Phase 1 scope
-------------
- A student submits one leave request covering a date/time range and any number
  of enrolled course offerings.
- Each course offering gets its own review row (comment/status/history) that is
  deliberately separate from the leave request's own status.
- Only Draft / Submitted / Cancelled are produced in Phase 1. The remaining
  workflow statuses are declared now so Phase 2 can add steps without a
  status-field migration.

Attendance is never written from leave data (spec §5.2): the roster only reads
these tables and displays a separate leave badge.
"""
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import models


def leave_attachment_upload_path(instance, filename: str) -> str:
    """Randomised, per-request path so original filenames never collide."""
    suffix = Path(filename).suffix.lower()[:16]
    return f"leave_attachments/{instance.leave_request_id}/{uuid.uuid4().hex}{suffix}"


class LeaveRequest(models.Model):
    """คำร้องลาของนักศึกษา — หนึ่งรายการเชื่อมได้หลายรายวิชา"""

    LEAVE_TYPE_CHOICES = (
        ("sick", "ลาป่วย"),
        ("personal", "ลากิจส่วนตัว"),
        ("other", "ลาอื่น ๆ"),
    )

    # Phase 2 statuses are declared up front; Phase 1 only writes draft,
    # submitted, and cancelled.
    STATUS_CHOICES = (
        ("draft", "แบบร่าง"),
        ("submitted", "ส่งคำร้องแล้ว"),
        ("pending_advisor_review", "รอความเห็นอาจารย์ที่ปรึกษา"),
        ("pending_program_head_review", "รอความเห็นหัวหน้าหน่วยหลักสูตร"),
        ("pending_final_approval", "รอผู้มีอำนาจอนุมัติ"),
        ("approved", "อนุญาต"),
        ("rejected", "ไม่อนุญาต"),
        ("returned", "ส่งกลับเพื่อแก้ไข"),
        ("cancelled", "ยกเลิกคำร้อง"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        "accounts.StudentProfile", on_delete=models.CASCADE,
        related_name="leave_requests", verbose_name="นักศึกษา",
    )
    leave_type = models.CharField(
        "ประเภทการลา", max_length=16, choices=LEAVE_TYPE_CHOICES, default="personal"
    )
    start_date = models.DateField("วันที่เริ่มลา")
    end_date = models.DateField("วันที่สิ้นสุดการลา")
    start_time = models.TimeField(
        "เวลาเริ่มลา (ถ้าระบุ)", null=True, blank=True,
        help_text="ไม่ระบุ = ลาทั้งวัน",
    )
    end_time = models.TimeField(
        "เวลาสิ้นสุดการลา (ถ้าระบุ)", null=True, blank=True,
        help_text="ต้องระบุคู่กับเวลาเริ่มลา",
    )
    reason = models.TextField("เหตุผลการลา")
    late_submission_reason = models.TextField(
        "เหตุผลการส่งย้อนหลัง", blank=True, default="",
        help_text="ใช้เมื่อลาป่วยและส่งหลังกำหนด แต่ยังอยู่ภายในระยะผ่อนผัน",
    )
    # Contact details from the college paper form (ใบลาป่วย/ลากิจส่วนตัว).
    contact_phone = models.CharField(
        "โทรศัพท์ที่ติดต่อได้ระหว่างลา", max_length=32, blank=True, default=""
    )
    line_id = models.CharField("LINE ID", max_length=64, blank=True, default="")
    address_during_leave = models.TextField(
        "ที่อยู่ระหว่างการลา", blank=True, default=""
    )
    guardian_acknowledged = models.BooleanField(
        "ผู้ปกครองรับทราบการลาแล้ว", default=False
    )
    guardian_phone = models.CharField(
        "โทรศัพท์ผู้ปกครอง", max_length=32, blank=True, default=""
    )
    guardian_address = models.TextField("ที่อยู่ผู้ปกครอง", blank=True, default="")
    status = models.CharField(
        "สถานะคำร้อง", max_length=32, choices=STATUS_CHOICES, default="draft"
    )
    submitted_at = models.DateTimeField("ส่งคำร้องเมื่อ", null=True, blank=True)
    cancelled_at = models.DateTimeField("ยกเลิกเมื่อ", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_requests"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["student", "status"]),
            models.Index(fields=["status", "start_date", "end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="leave_end_date_not_before_start",
            ),
        ]

    def clean(self):
        if self.end_date and self.start_date and self.end_date < self.start_date:
            raise ValidationError("วันที่สิ้นสุดการลาต้องไม่ก่อนวันที่เริ่มลา")
        if bool(self.start_time) != bool(self.end_time):
            raise ValidationError("ต้องระบุเวลาเริ่มและเวลาสิ้นสุดพร้อมกัน หรือไม่ระบุทั้งคู่")
        if (
            self.start_time and self.end_time
            and self.start_date == self.end_date
            and self.end_time <= self.start_time
        ):
            raise ValidationError("เวลาสิ้นสุดการลาต้องอยู่หลังเวลาเริ่มลา")

    @property
    def total_days(self) -> int:
        """Inclusive number of leave days (form: มีกำหนดเวลา ... วัน)."""
        if not self.start_date or not self.end_date:
            return 0
        return (self.end_date - self.start_date).days + 1

    @property
    def is_editable(self) -> bool:
        return self.status in ("draft", "returned")

    @property
    def is_cancellable(self) -> bool:
        return self.status in (
            "draft",
            "submitted",
            "pending_advisor_review",
            "pending_program_head_review",
            "pending_final_approval",
            "returned",
        )

    def __str__(self):
        return f"{self.student.student_code} {self.start_date}–{self.end_date} ({self.status})"


class LeaveAttachment(models.Model):
    """ไฟล์แนบของคำร้อง (ใบรับรองแพทย์ ฯลฯ) — เก็บนอก public media root.

    Downloads are served by an authenticated, role-scoped endpoint; the file
    path itself is never exposed to the client.
    """

    TYPE_CHOICES = (
        ("medical_certificate", "ใบรับรองแพทย์"),
        ("other", "เอกสารประกอบอื่น"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="attachments",
        verbose_name="คำร้องลา",
    )
    attachment_type = models.CharField(
        "ประเภทไฟล์แนบ", max_length=32, choices=TYPE_CHOICES,
        default="medical_certificate",
    )
    file = models.FileField(
        "ไฟล์แนบ", upload_to=leave_attachment_upload_path, max_length=500,
    )
    original_name = models.CharField("ชื่อไฟล์เดิม", max_length=255)
    content_type = models.CharField("ชนิดไฟล์", max_length=100, blank=True, default="")
    size = models.PositiveBigIntegerField("ขนาดไฟล์ (bytes)", default=0)
    uploaded_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_attachments_uploaded", verbose_name="ผู้อัปโหลด",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leave_attachments"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["leave_request", "attachment_type"]),
        ]

    def __str__(self):
        return f"{self.original_name} ({self.attachment_type})"


class LeaveCourse(models.Model):
    """รายวิชาที่ได้รับผลกระทบ พร้อมสถานะการพิจารณารายวิชา (แยกจากคำร้องหลัก)"""

    REVIEW_STATUS_CHOICES = (
        ("pending", "รอการพิจารณา"),
        ("reviewed", "ให้ความเห็นแล้ว"),
        ("acknowledged", "รับทราบ"),
        ("rejected", "ไม่เห็นด้วย"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="courses",
        verbose_name="คำร้องลา",
    )
    course_offering = models.ForeignKey(
        "courses.CourseOffering", on_delete=models.PROTECT,
        related_name="leave_courses", verbose_name="รายวิชาที่เปิดสอน",
    )
    # Snapshot of the affected window for this course. Phase 1 copies the
    # request window; Phase 2 may narrow it per course.
    affected_start_date = models.DateField("วันที่เริ่มได้รับผลกระทบ")
    affected_end_date = models.DateField("วันที่สิ้นสุดได้รับผลกระทบ")
    affected_start_time = models.TimeField(
        "เวลาเริ่มได้รับผลกระทบ", null=True, blank=True
    )
    affected_end_time = models.TimeField(
        "เวลาสิ้นสุดได้รับผลกระทบ", null=True, blank=True
    )
    review_status = models.CharField(
        "สถานะการพิจารณารายวิชา", max_length=16,
        choices=REVIEW_STATUS_CHOICES, default="pending",
    )
    reviewed_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_course_reviews_done", verbose_name="ผู้พิจารณาล่าสุด",
    )
    reviewed_at = models.DateTimeField("พิจารณาล่าสุดเมื่อ", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_courses"
        ordering = ["course_offering__course__course_code"]
        constraints = [
            models.UniqueConstraint(
                fields=["leave_request", "course_offering"],
                name="uniq_leave_course_per_request",
            ),
        ]
        indexes = [
            models.Index(fields=["course_offering", "review_status"]),
        ]

    def __str__(self):
        return f"{self.leave_request_id} → {self.course_offering_id} ({self.review_status})"


class LeaveCourseReview(models.Model):
    """ประวัติการพิจารณารายวิชา — เก็บทุกครั้งที่อาจารย์บันทึก เพื่อไม่ทับประวัติเดิม"""

    STATUS_CHOICES = LeaveCourse.REVIEW_STATUS_CHOICES[1:]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_course = models.ForeignKey(
        LeaveCourse, on_delete=models.CASCADE, related_name="reviews",
        verbose_name="รายวิชาที่พิจารณา",
    )
    reviewer = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT,
        related_name="leave_course_review_history", verbose_name="ผู้พิจารณา",
    )
    review_status = models.CharField(
        "ผลการพิจารณา", max_length=16, choices=STATUS_CHOICES
    )
    comment = models.TextField("ความคิดเห็น", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leave_course_reviews"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.leave_course_id} {self.review_status}"


class LeaveRoleAssignment(models.Model):
    """Phase 2 workflow role assignments (table created now, no UI yet).

    Kept separate from `User.role` because advisor / program-head / final
    approver assignments are scoped by program, class group, or term.
    """

    ROLE_CHOICES = (
        ("advisor", "อาจารย์ที่ปรึกษา"),
        ("program_head", "หัวหน้าหน่วยหลักสูตร"),
        ("final_approver", "ผู้มีอำนาจอนุมัติ"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE,
        related_name="leave_role_assignments", verbose_name="ผู้รับผิดชอบ",
    )
    role_type = models.CharField("บทบาทใน Workflow", max_length=24, choices=ROLE_CHOICES)
    program = models.ForeignKey(
        "academics.Program", on_delete=models.CASCADE, null=True, blank=True,
        related_name="leave_role_assignments", verbose_name="หลักสูตร",
    )
    class_group = models.ForeignKey(
        "academics.ClassGroup", on_delete=models.CASCADE, null=True, blank=True,
        related_name="leave_role_assignments", verbose_name="กลุ่มเรียน",
    )
    academic_term = models.ForeignKey(
        "academics.AcademicTerm", on_delete=models.CASCADE, null=True, blank=True,
        related_name="leave_role_assignments", verbose_name="ภาคการศึกษา",
    )
    is_active = models.BooleanField("เปิดใช้งาน", default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_role_assignments"
        ordering = ["role_type", "user__username"]
        indexes = [
            models.Index(fields=["role_type", "is_active"]),
        ]

    def __str__(self):
        return f"{self.get_role_type_display()} — {self.user}"


class LeaveWorkflowStep(models.Model):
    """One approval step of a submitted leave request.

    Steps are created when a draft is submitted so the request always has a
    concrete assignee snapshot. Re-assigning a role later never rewrites the
    steps of requests that are already in flight.
    """

    STATUS_CHOICES = (
        ("pending", "รอดำเนินการ"),
        ("completed", "ดำเนินการแล้ว"),
        ("skipped", "ข้ามขั้นตอน"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="workflow_steps",
        verbose_name="คำร้องลา",
    )
    step_order = models.PositiveSmallIntegerField("ลำดับขั้นตอน")
    role_type = models.CharField(
        "บทบาทใน Workflow", max_length=24,
        choices=LeaveRoleAssignment.ROLE_CHOICES,
    )
    assignee = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_workflow_steps", verbose_name="ผู้รับผิดชอบ",
    )
    status = models.CharField(
        "สถานะขั้นตอน", max_length=16, choices=STATUS_CHOICES, default="pending"
    )
    acted_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_workflow_actions", verbose_name="ผู้ดำเนินการ",
    )
    acted_at = models.DateTimeField("ดำเนินการเมื่อ", null=True, blank=True)
    comment = models.TextField("ความเห็น/เหตุผล", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "leave_workflow_steps"
        ordering = ["step_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["leave_request", "step_order"],
                name="uniq_leave_workflow_step_order",
            ),
        ]
        indexes = [
            models.Index(fields=["role_type", "status"]),
            models.Index(fields=["assignee", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.leave_request_id} #{self.step_order} "
            f"{self.role_type} ({self.status})"
        )


class LeaveWorkflowHistory(models.Model):
    """Append-only business history shown to students and approvers.

    This is deliberately separate from `audit.AuditLog`: the audit log is the
    security trail (IP/user agent, admin-only), while this table is the
    workflow timeline that the student is allowed to read.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="workflow_history",
        verbose_name="คำร้องลา",
    )
    step_order = models.PositiveSmallIntegerField("ลำดับขั้นตอน", null=True, blank=True)
    role_type = models.CharField("บทบาทใน Workflow", max_length=24, blank=True, default="")
    action = models.CharField("การดำเนินการ", max_length=32)
    from_status = models.CharField("สถานะก่อนดำเนินการ", max_length=32, blank=True, default="")
    to_status = models.CharField("สถานะหลังดำเนินการ", max_length=32, blank=True, default="")
    actor = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="leave_workflow_history", verbose_name="ผู้ดำเนินการ",
    )
    comment = models.TextField("ความเห็น/เหตุผล", blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leave_workflow_history"
        ordering = ["created_at", "step_order"]
        indexes = [
            models.Index(fields=["leave_request", "created_at"]),
        ]

    def __str__(self):
        return f"{self.leave_request_id} {self.action}"
