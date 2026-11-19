"""Django admin registration for leave data (support/operations only)."""
from django.contrib import admin

from apps.leaves.models import (
    LeaveAttachment,
    LeaveCourse,
    LeaveCourseReview,
    LeavePolicyConfig,
    LeaveRequest,
    LeaveRoleAssignment,
    LeaveWorkflowConfig,
    LeaveWorkflowHistory,
    LeaveWorkflowStep,
)


class LeaveCourseInline(admin.TabularInline):
    model = LeaveCourse
    extra = 0
    readonly_fields = ["review_status", "reviewed_by", "reviewed_at"]


class LeaveAttachmentInline(admin.TabularInline):
    model = LeaveAttachment
    extra = 0
    readonly_fields = ["original_name", "size", "content_type", "uploaded_by", "created_at"]


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = [
        "student", "leave_type", "start_date", "end_date", "status", "created_at",
    ]
    list_filter = ["status", "leave_type"]
    search_fields = [
        "student__student_code", "student__first_name", "student__last_name",
    ]
    readonly_fields = ["submitted_at", "cancelled_at", "created_at", "updated_at"]
    inlines = [LeaveCourseInline, LeaveAttachmentInline]


@admin.register(LeaveCourse)
class LeaveCourseAdmin(admin.ModelAdmin):
    list_display = [
        "leave_request", "course_offering", "review_status", "reviewed_by",
    ]
    list_filter = ["review_status"]
    search_fields = [
        "leave_request__student__student_code",
        "course_offering__course__course_code",
    ]


@admin.register(LeaveCourseReview)
class LeaveCourseReviewAdmin(admin.ModelAdmin):
    list_display = ["leave_course", "review_status", "reviewer", "created_at"]
    list_filter = ["review_status"]


@admin.register(LeaveRoleAssignment)
class LeaveRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ["user", "role_type", "program", "class_group", "is_active"]
    list_filter = ["role_type", "is_active"]


@admin.register(LeaveWorkflowConfig)
class LeaveWorkflowConfigAdmin(admin.ModelAdmin):
    list_display = ["name", "program", "class_group", "academic_term", "steps", "is_active"]
    list_filter = ["is_active", "program", "academic_term"]
    search_fields = ["name", "program__program_name", "class_group__group_name"]


@admin.register(LeavePolicyConfig)
class LeavePolicyConfigAdmin(admin.ModelAdmin):
    list_display = [
        "personal_advance_days", "sick_normal_grace_days",
        "sick_late_grace_days", "medical_certificate_min_days", "updated_at",
    ]
    readonly_fields = ["updated_at"]
    fieldsets = (
        (None, {
            "fields": (
                "personal_advance_days", "sick_normal_grace_days",
                "sick_late_grace_days", "medical_certificate_min_days",
                "updated_at",
            ),
            "description": (
                "ตั้งค่าได้ครั้งละหนึ่งแถวสำหรับทั้งระบบ การเปลี่ยนแปลงมีผลทันที"
                "กับการส่งคำร้องใหม่และวันกำหนดที่แสดงในคำร้องเดิม"
            ),
        }),
    )

    def has_add_permission(self, request):
        return not LeavePolicyConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LeaveWorkflowStep)
class LeaveWorkflowStepAdmin(admin.ModelAdmin):
    list_display = [
        "leave_request", "step_order", "role_type", "assignee", "status",
        "acted_by", "acted_at",
    ]
    list_filter = ["role_type", "status"]
    search_fields = [
        "leave_request__student__student_code", "assignee__username",
    ]


@admin.register(LeaveWorkflowHistory)
class LeaveWorkflowHistoryAdmin(admin.ModelAdmin):
    list_display = [
        "leave_request", "action", "from_status", "to_status", "actor",
        "created_at",
    ]
    list_filter = ["action"]
    search_fields = ["leave_request__student__student_code"]
    readonly_fields = [
        "leave_request", "step_order", "role_type", "action",
        "from_status", "to_status", "actor", "comment", "created_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
