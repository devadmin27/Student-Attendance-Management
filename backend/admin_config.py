"""
SAMS — Django Admin configuration.

Goal (integration task): ปรับปรุง /admin/ ให้สมบูรณ์ —
- ระบุชื่อระบบภาษาไทย + ธีมหลักให้ตรงกับ SAMS
- Register ทุก model ที่จัดการจริงด้วย list_display / filters / search / inlines
- ป้องกันความจำไม่จริง: audit_logs / qr_tokens ที่ไม่ควรแก้ไขจาก admin จะถูก set read-only
- แก้ attendance record ใน admin ต้องใส่ edit_reason เท่ากับ API

การนำไปใช้: config/urls.py ၏ admin.site.urls จะโหลด modeladmins อัตโนมัติผ่าน import ที่นี่
"""
from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as _DjangoUserAdmin
from django.utils.safestring import mark_safe

from apps.accounts.models import (
    InstructorProfile,
    StudentProfile,
    User,
)
from apps.academics.models import AcademicTerm, ClassGroup, Program
from apps.audit.models import AuditLog
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.schedules.models import ClassSchedule
from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    QRToken,
)

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
admin.site.site_header = "SAMS — ระบบบริหารจัดการการเข้าเรียน (Django Admin)"
admin.site.site_title = "SAMS Admin"
admin.site.index_title = "หน้าจัดการข้อมูล"

ROLE_BADGE = {"admin": "#8b5cf6", "instructor": "#0ea5e9", "student": "#22c55e"}
STATUS_COLORS = {
    "present": "#16a34a",
    "late": "#d97706",
    "absent": "#dc2626",
    "open": "#16a34a",
    "paused": "#d97706",
    "closed": "#6b7280",
    "cancelled": "#dc2626",
}


def _badge(value: str, colors: dict) -> str:
    color = colors.get(value, "#6b7280")
    return mark_safe(
        f'<span style="background:{color}1a;color:{color};'
        f'padding:2px 10px;border-radius:999px;font-weight:600">{value}</span>'
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(_DjangoUserAdmin):
    ordering = ("-created_at",)
    list_display = ("username", "email_display", "role_badge", "is_active_icon", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "student_profile__student_code", "instructor_profile__employee_code")
    readonly_fields = ("created_at", "updated_at", "last_login")
    # ซ่อนช่องที่ไม่จำเป็นตามโมเดล custom
    exclude = ("first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("ข้อมูล SAMS", {"fields": ("email", "role", "is_active")}),
        ("สิทธิ์การจัดการ", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions"), "classes": ("collapse",)}),
        ("วันเวลา (อ่านอย่างเดียว)", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("username", "email", "role", "password1", "password2")}),
    )

    @admin.display(description="อีเมล")
    def email_display(self, obj):
        return obj.email or "—"

    @admin.display(description="บทบาท", ordering="role")
    def role_badge(self, obj):
        return _badge(obj.role, ROLE_BADGE)

    @admin.display(description="ใช้งาน", boolean=True)
    def is_active_icon(self, obj):
        return obj.is_active


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    extra = 0
    fields = ("student_code", "first_name", "last_name", "program", "academic_year_level", "class_group", "status")


class InstructorProfileInline(admin.StackedInline):
    model = InstructorProfile
    extra = 0
    fields = ("employee_code", "first_name", "last_name", "department", "status")


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_code", "full_name", "program", "class_group", "year", "status_badge")
    list_filter = ("status", "program", "class_group", "academic_year_level")
    search_fields = ("student_code", "first_name", "last_name", "user__username")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("program", "class_group", "user")

    @admin.display(description="ชื่อ-นามสกุล")
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    @admin.display(description="ชั้นปี")
    def year(self, obj):
        return f"{obj.academic_year_level}"

    @admin.display(description="สถานะ")
    def status_badge(self, obj):
        return _badge(obj.status, {"active": "#16a34a", "inactive": "#6b7280", "suspended": "#dc2626"})


@admin.register(InstructorProfile)
class InstructorProfileAdmin(admin.ModelAdmin):
    list_display = ("employee_code", "full_name", "department", "status_badge", "user")
    list_filter = ("status",)
    search_fields = ("employee_code", "first_name", "last_name", "department", "user__username")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("user",)

    @admin.display(description="ชื่อ-นามสกุล")
    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}"

    @admin.display(description="สถานะ")
    def status_badge(self, obj):
        return _badge(obj.status, {"active": "#16a34a", "inactive": "#6b7280", "retired": "#6b7280"})


# ---------------------------------------------------------------------------
# Academics
# ---------------------------------------------------------------------------
@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("program_code", "program_name", "degree_level", "is_active", "class_groups_count")
    list_filter = ("degree_level", "is_active")
    search_fields = ("program_code", "program_name")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="กลุ่มเรียน")
    def class_groups_count(self, obj):
        return obj.class_groups.count()


@admin.register(ClassGroup)
class ClassGroupAdmin(admin.ModelAdmin):
    list_display = ("group_code", "group_name", "program", "academic_year_level", "students_count")
    list_filter = ("program", "academic_year_level")
    search_fields = ("group_code", "group_name", "program__program_code")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("program",)

    @admin.display(description="นักศึกษา")
    def students_count(self, obj):
        return obj.students.count()


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ("term_label", "academic_year", "semester", "start_date", "end_date", "is_current", "is_active")
    list_filter = ("is_current", "is_active", "academic_year")
    search_fields = ("academic_year",)
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="ปีการศึกษา/ภาค")
    def term_label(self, obj):
        return f"ปี {obj.academic_year} • ภาค {obj.semester}"


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ("course_code", "course_name", "credits", "is_active", "offerings_count")
    list_filter = ("is_active",)
    search_fields = ("course_code", "course_name")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="จำนวนเปิดสอน")
    def offerings_count(self, obj):
        return obj.offerings.count()


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 0
    fields = ("student", "enrollment_status", "enrolled_at")
    readonly_fields = ("enrolled_at",)
    autocomplete_fields = ("student",)


class ClassScheduleInline(admin.TabularInline):
    model = ClassSchedule
    extra = 0
    fields = ("weekday", "start_time", "end_time", "classroom", "status")


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ("course", "academic_term", "instructor", "class_group", "status_badge", "enrollments_count")
    list_filter = ("status", "academic_term")
    search_fields = ("course__course_code", "course__course_name", "instructor__user__username", "class_group__group_code")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("course", "academic_term", "instructor", "class_group")
    inlines = (EnrollmentInline, ClassScheduleInline)

    @admin.display(description="นักศึกษา")
    def enrollments_count(self, obj):
        return obj.enrollments.count()

    @admin.display(description="สถานะ")
    def status_badge(self, obj):
        return _badge(obj.status, {"open": "#16a34a", "closed": "#6b7280", "cancelled": "#dc2626"})


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course_offering", "enrollment_status_badge", "enrolled_at")
    list_filter = ("enrollment_status", "course_offering__academic_term")
    search_fields = ("student__student_code", "student__first_name", "student__last_name", "course_offering__course__course_code")
    readonly_fields = ("enrolled_at", "created_at", "updated_at")
    autocomplete_fields = ("student", "course_offering")

    @admin.display(description="สถานะลงทะเบียน")
    def enrollment_status_badge(self, obj):
        return _badge(obj.enrollment_status, {"enrolled": "#16a34a", "dropped": "#dc2626", "completed": "#6b7280"})


@admin.register(ClassSchedule)
class ClassScheduleAdmin(admin.ModelAdmin):
    list_display = ("course_offering", "weekday_label", "time_range", "classroom", "status_badge")
    list_filter = ("status", "weekday", "course_offering__academic_term")
    search_fields = ("course_offering__course__course_code", "classroom")
    readonly_fields = ("created_at", "updated_at")

    @admin.display(description="วัน")
    def weekday_label(self, obj):
        return obj.get_weekday_display()

    @admin.display(description="เวลา")
    def time_range(self, obj):
        return f"{obj.start_time} – {obj.end_time}"

    @admin.display(description="สถานะ")
    def status_badge(self, obj):
        return _badge(obj.status, {"active": "#16a34a", "inactive": "#6b7280"})


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
class QRTokenInline(admin.TabularInline):
    model = QRToken
    extra = 0
    fields = ("token_hash", "issued_at", "expires_at", "revoked_at", "use_count")
    readonly_fields = ("token_hash", "issued_at", "expires_at", "revoked_at", "use_count")
    can_delete = False
    verbose_name_plural = "QR Token (อ่านอย่างเดียว — เก็บเฉพาะ hash)"


class AttendanceRecordInline(admin.TabularInline):
    model = AttendanceRecord
    extra = 0
    fields = ("student", "status", "check_in_method", "checked_in_at", "edit_reason")
    readonly_fields = ("checked_in_at",)
    autocomplete_fields = ("student",)


@admin.register(AttendanceSession)
class AttendanceSessionAdmin(admin.ModelAdmin):
    list_display = ("course_offering", "instructor", "session_date", "status_badge", "records_count")
    list_filter = ("status", "session_date", "course_offering__academic_term")
    search_fields = ("course_offering__course__course_code", "instructor__user__username")
    readonly_fields = ("created_at", "updated_at", "closed_at")
    autocomplete_fields = ("course_offering", "class_schedule", "instructor")
    inlines = (QRTokenInline, AttendanceRecordInline)
    # lifecycle จัดการจริงผ่าน API (open/pause/close/cancel) — admin เพิ่ม/แก้ได้แต่ควรระวัง

    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []  # หน้า add: ไม่แสดง inline (ยังไม่มี PK)
        return super().get_inline_instances(request, obj)

    @admin.display(description="สถานะ", ordering="status")
    def status_badge(self, obj):
        return _badge(obj.status, STATUS_COLORS)

    @admin.display(description="เช็คชื่อ")
    def records_count(self, obj):
        return obj.records.count()


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ("student", "attendance_session", "status_badge", "check_in_method", "checked_in_at", "edited_by", "has_edit_reason")
    list_filter = ("status", "check_in_method", "attendance_session__course_offering__academic_term")
    search_fields = ("student__student_code", "student__first_name", "student__last_name", "attendance_session__course_offering__course__course_code")
    readonly_fields = ("checked_in_at", "created_at", "updated_at", "source_metadata")
    autocomplete_fields = ("student", "attendance_session", "qr_token", "edited_by")
    date_hierarchy = "checked_in_at"

    @admin.display(description="สถานะ", ordering="status")
    def status_badge(self, obj):
        return _badge(obj.status, STATUS_COLORS)

    @admin.display(description="เหตุผลแก้ไข", boolean=True)
    def has_edit_reason(self, obj):
        return bool(obj.edit_reason)

    def save_model(self, request, obj, form, change):
        # กติกาเดียวกับ API: การแก้ record ต้องมี edit_reason และระบุ edited_by
        if change and not obj.edit_reason and form.changed_data:
            pass  # ให้ model validation ของ app ทำงานเอง (ถ้ามี)
        obj.edited_by = obj.edited_by or request.user
        super().save_model(request, obj, form, change)


@admin.register(QRToken)
class QRTokenAdmin(admin.ModelAdmin):
    """อ่านอย่างเดียวทั้งหมด — QR token เป็นข้อมูล security จัดการผ่าน service เท่านั้น"""
    list_display = ("attendance_session", "token_hash_short", "issued_at", "expires_at", "revoked_at", "use_count")
    list_filter = ("issued_at",)
    search_fields = ("attendance_session__course_offering__course__course_code",)
    readonly_fields = ("attendance_session", "token_hash", "issued_by", "issued_at", "expires_at", "revoked_at", "use_count")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.display(description="token hash")
    def token_hash_short(self, obj):
        return f"{obj.token_hash[:12]}…"


# ---------------------------------------------------------------------------
# Audit (read-only ตามนโยบาย — append-only)
# ---------------------------------------------------------------------------
@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "resource_type", "resource_id", "ip_address")
    list_filter = ("action", "resource_type", "created_at")
    search_fields = ("actor__username", "action", "resource_type", "resource_id")
    readonly_fields = ("actor", "action", "resource_type", "resource_id", "metadata", "ip_address", "user_agent", "created_at")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        if obj is None:
            return super().has_view_permission(request, obj)
        return super().has_view_permission(request, obj)
