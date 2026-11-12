"""Serializers for leave requests, available courses, and course reviews."""
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.leaves import services
from apps.leaves.models import (
    LeaveAttachment,
    LeaveCourse,
    LeaveCourseReview,
    LeaveRequest,
)


class LeaveCourseReviewSerializer(serializers.ModelSerializer):
    reviewer_name = serializers.SerializerMethodField()
    reviewer_username = serializers.CharField(source="reviewer.username", read_only=True)
    review_status_display = serializers.CharField(
        source="get_review_status_display", read_only=True
    )

    class Meta:
        model = LeaveCourseReview
        fields = [
            "id", "review_status", "review_status_display", "comment",
            "reviewer", "reviewer_username", "reviewer_name", "created_at",
        ]
        read_only_fields = fields

    def get_reviewer_name(self, obj):
        profile = getattr(obj.reviewer, "instructor_profile", None)
        if profile is None:
            return obj.reviewer.username
        return f"{profile.first_name} {profile.last_name}".strip()


class LeaveCourseSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course_offering.course.course_code", read_only=True)
    course_name = serializers.CharField(source="course_offering.course.course_name", read_only=True)
    term_label = serializers.SerializerMethodField()
    class_group_name = serializers.SerializerMethodField()
    schedules = serializers.SerializerMethodField()
    review_status_display = serializers.CharField(
        source="get_review_status_display", read_only=True
    )
    reviewed_by_name = serializers.SerializerMethodField()
    reviews = LeaveCourseReviewSerializer(many=True, read_only=True)

    class Meta:
        model = LeaveCourse
        fields = [
            "id", "course_offering", "course_code", "course_name", "term_label",
            "class_group_name", "schedules",
            "affected_start_date", "affected_end_date",
            "affected_start_time", "affected_end_time",
            "review_status", "review_status_display",
            "reviewed_by", "reviewed_by_name", "reviewed_at",
            "reviews", "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_term_label(self, obj):
        term = obj.course_offering.academic_term
        return f"{term.academic_year}/{term.semester}"

    def get_class_group_name(self, obj):
        group = obj.course_offering.class_group
        return group.group_name if group else None

    def get_schedules(self, obj):
        return [
            {
                "weekday": schedule.weekday,
                "weekday_display": schedule.get_weekday_display(),
                "start_time": schedule.start_time.strftime("%H:%M"),
                "end_time": schedule.end_time.strftime("%H:%M"),
                "classroom": schedule.classroom,
            }
            for schedule in obj.course_offering.schedules.all()
            if schedule.status != "cancelled"
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by_id is None:
            return None
        profile = getattr(obj.reviewed_by, "instructor_profile", None)
        if profile is None:
            return obj.reviewed_by.username
        return f"{profile.first_name} {profile.last_name}".strip()


class LeaveAttachmentSerializer(serializers.ModelSerializer):
    """Read-only attachment metadata. The file itself is never exposed."""

    attachment_type_display = serializers.CharField(
        source="get_attachment_type_display", read_only=True
    )
    uploaded_by_name = serializers.SerializerMethodField()
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = LeaveAttachment
        fields = [
            "id", "attachment_type", "attachment_type_display",
            "original_name", "content_type", "size",
            "uploaded_by", "uploaded_by_name", "download_url", "created_at",
        ]
        read_only_fields = fields

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by_id is None:
            return None
        return obj.uploaded_by.get_full_name() or obj.uploaded_by.username

    def get_download_url(self, obj):
        return (
            f"/leave-requests/{obj.leave_request_id}/attachments/"
            f"{obj.id}/download/"
        )


class LeaveAttachmentWriteSerializer(serializers.Serializer):
    file = serializers.FileField()
    attachment_type = serializers.ChoiceField(
        choices=LeaveAttachment.TYPE_CHOICES,
        required=False,
        default="medical_certificate",
    )

    def validate_file(self, value):
        suffix = Path(value.name).suffix.lower().lstrip(".")
        if suffix not in settings.LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS:
            allowed = ", ".join(settings.LEAVE_ATTACHMENT_ALLOWED_EXTENSIONS)
            raise serializers.ValidationError(
                f"ชนิดไฟล์ไม่รองรับ — รองรับเฉพาะ {allowed}"
            )
        if value.size > settings.LEAVE_ATTACHMENT_MAX_BYTES:
            max_mb = settings.LEAVE_ATTACHMENT_MAX_BYTES / (1024 * 1024)
            raise serializers.ValidationError(
                f"ไฟล์มีขนาดใหญ่เกินกำหนด (สูงสุด {max_mb:g} MB)"
            )
        content_type = (getattr(value, "content_type", "") or "").lower()
        allowed_types = set(settings.LEAVE_ATTACHMENT_ALLOWED_CONTENT_TYPES)
        if content_type and content_type not in allowed_types | {
            "application/octet-stream"
        }:
            raise serializers.ValidationError("ชนิดไฟล์ไม่ตรงกับนามสกุลที่รองรับ")
        return value


class LeaveRequestSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    student_program_name = serializers.SerializerMethodField()
    student_class_group_name = serializers.SerializerMethodField()
    student_year_level = serializers.IntegerField(
        source="student.academic_year_level", read_only=True
    )
    leave_type_display = serializers.CharField(
        source="get_leave_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_days = serializers.IntegerField(read_only=True)
    courses = LeaveCourseSerializer(many=True, read_only=True)
    course_count = serializers.IntegerField(source="courses.count", read_only=True)
    attachments = LeaveAttachmentSerializer(many=True, read_only=True)
    requires_medical_certificate = serializers.SerializerMethodField()
    medical_certificate_attached = serializers.SerializerMethodField()
    submission_deadline = serializers.SerializerMethodField()
    submission_grace_deadline = serializers.SerializerMethodField()
    is_editable = serializers.BooleanField(read_only=True)
    is_cancellable = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "student", "student_code", "student_name",
            "student_program_name", "student_class_group_name", "student_year_level",
            "leave_type", "leave_type_display",
            "start_date", "end_date", "start_time", "end_time", "total_days",
            "reason", "late_submission_reason",
            "contact_phone", "line_id", "address_during_leave",
            "guardian_acknowledged", "guardian_phone", "guardian_address",
            "status", "status_display",
            "submitted_at", "cancelled_at",
            "attachments", "requires_medical_certificate",
            "medical_certificate_attached",
            "submission_deadline", "submission_grace_deadline",
            "course_count", "courses", "is_editable", "is_cancellable",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_student_program_name(self, obj):
        program = obj.student.program
        return program.program_name if program else None

    def get_student_class_group_name(self, obj):
        group = obj.student.class_group
        return group.group_name if group else None

    def get_requires_medical_certificate(self, obj):
        return services.requires_medical_certificate(obj)

    def get_medical_certificate_attached(self, obj):
        return any(
            attachment.attachment_type == "medical_certificate"
            for attachment in obj.attachments.all()
        )

    def get_submission_deadline(self, obj):
        normal, _ = services.submission_deadlines(
            obj.leave_type, obj.start_date, obj.end_date
        )
        return normal.isoformat() if normal else None

    def get_submission_grace_deadline(self, obj):
        _, grace = services.submission_deadlines(
            obj.leave_type, obj.start_date, obj.end_date
        )
        return grace.isoformat() if grace else None


class LeaveRequestWriteSerializer(serializers.ModelSerializer):
    """Create/update a draft. Status and ownership are server-controlled."""

    course_offering_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = LeaveRequest
        fields = [
            "leave_type", "start_date", "end_date", "start_time", "end_time",
            "reason", "late_submission_reason",
            "contact_phone", "line_id", "address_during_leave",
            "guardian_acknowledged", "guardian_phone", "guardian_address",
            "course_offering_ids",
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        services.validate_leave_range(start_date, end_date, start_time, end_time)
        for field in ("contact_phone", "guardian_phone"):
            value = attrs.get(field, getattr(self.instance, field, "")) or ""
            digits = re.sub(r"\D", "", value)
            if value and not 9 <= len(digits) <= 10:
                raise serializers.ValidationError(
                    {field: "กรุณาระบุหมายเลขโทรศัพท์ 9–10 หลัก"}
                )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        offering_ids = validated_data.pop("course_offering_ids", [])
        user = self.context["request"].user
        student = getattr(user, "student_profile", None)
        if student is None:
            raise serializers.ValidationError(
                {"detail": "บัญชีนี้ยังไม่มีโปรไฟล์นักศึกษา"}
            )
        leave_request = LeaveRequest.objects.create(
            student=student, status="draft", **validated_data
        )
        services.set_courses(leave_request, offering_ids)
        return leave_request

    @transaction.atomic
    def update(self, instance, validated_data):
        offering_ids = validated_data.pop("course_offering_ids", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if offering_ids is not None:
            services.set_courses(instance, offering_ids)
        else:
            services.refresh_affected_windows(instance)
        return instance


class LeaveCourseInboxSerializer(serializers.ModelSerializer):
    """Instructor's course-scoped view of a leave request."""

    leave_request_id = serializers.UUIDField(source="leave_request.id", read_only=True)
    request_status = serializers.CharField(source="leave_request.status", read_only=True)
    request_status_display = serializers.CharField(
        source="leave_request.get_status_display", read_only=True
    )
    student_code = serializers.CharField(
        source="leave_request.student.student_code", read_only=True
    )
    student_name = serializers.SerializerMethodField()
    leave_type = serializers.CharField(source="leave_request.leave_type", read_only=True)
    leave_type_display = serializers.CharField(
        source="leave_request.get_leave_type_display", read_only=True
    )
    start_date = serializers.DateField(source="leave_request.start_date", read_only=True)
    end_date = serializers.DateField(source="leave_request.end_date", read_only=True)
    start_time = serializers.TimeField(
        source="leave_request.start_time", read_only=True, allow_null=True
    )
    end_time = serializers.TimeField(
        source="leave_request.end_time", read_only=True, allow_null=True
    )
    reason = serializers.CharField(source="leave_request.reason", read_only=True)
    late_submission_reason = serializers.CharField(
        source="leave_request.late_submission_reason", read_only=True
    )
    submitted_at = serializers.DateTimeField(
        source="leave_request.submitted_at", read_only=True, allow_null=True
    )
    attachments = LeaveAttachmentSerializer(
        source="leave_request.attachments", many=True, read_only=True
    )
    requires_medical_certificate = serializers.SerializerMethodField()
    medical_certificate_attached = serializers.SerializerMethodField()
    course_code = serializers.CharField(
        source="course_offering.course.course_code", read_only=True
    )
    course_name = serializers.CharField(
        source="course_offering.course.course_name", read_only=True
    )
    term_label = serializers.SerializerMethodField()
    class_group_name = serializers.SerializerMethodField()
    review_status_display = serializers.CharField(
        source="get_review_status_display", read_only=True
    )
    reviews = LeaveCourseReviewSerializer(many=True, read_only=True)
    is_reviewable = serializers.SerializerMethodField()

    class Meta:
        model = LeaveCourse
        fields = [
            "id", "leave_request_id", "request_status", "request_status_display",
            "student_code", "student_name", "leave_type", "leave_type_display",
            "start_date", "end_date", "start_time", "end_time", "reason",
            "late_submission_reason", "submitted_at",
            "attachments", "requires_medical_certificate",
            "medical_certificate_attached",
            "course_offering", "course_code", "course_name",
            "term_label", "class_group_name",
            "affected_start_date", "affected_end_date",
            "affected_start_time", "affected_end_time",
            "review_status", "review_status_display", "reviewed_by",
            "reviewed_at", "reviews", "is_reviewable",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        student = obj.leave_request.student
        return f"{student.first_name} {student.last_name}".strip()

    def get_term_label(self, obj):
        term = obj.course_offering.academic_term
        return f"{term.academic_year}/{term.semester}"

    def get_class_group_name(self, obj):
        group = obj.course_offering.class_group
        return group.group_name if group else None

    def get_is_reviewable(self, obj):
        return obj.leave_request.status == "submitted"

    def get_requires_medical_certificate(self, obj):
        return services.requires_medical_certificate(obj.leave_request)

    def get_medical_certificate_attached(self, obj):
        return any(
            attachment.attachment_type == "medical_certificate"
            for attachment in obj.leave_request.attachments.all()
        )


class LeaveCoursePrintSerializer(serializers.ModelSerializer):
    """Course block for the printable A4 leave document."""

    course_code = serializers.CharField(
        source="course_offering.course.course_code", read_only=True
    )
    course_name = serializers.CharField(
        source="course_offering.course.course_name", read_only=True
    )
    term_label = serializers.SerializerMethodField()
    class_group_name = serializers.SerializerMethodField()
    instructor_names = serializers.SerializerMethodField()
    schedules = serializers.SerializerMethodField()
    review_status_display = serializers.CharField(
        source="get_review_status_display", read_only=True
    )
    reviews = LeaveCourseReviewSerializer(many=True, read_only=True)

    class Meta:
        model = LeaveCourse
        fields = [
            "id", "course_code", "course_name", "term_label", "class_group_name",
            "instructor_names", "schedules",
            "affected_start_date", "affected_end_date",
            "affected_start_time", "affected_end_time",
            "review_status", "review_status_display", "reviewed_at", "reviews",
        ]
        read_only_fields = fields

    def get_term_label(self, obj):
        term = obj.course_offering.academic_term
        return f"{term.academic_year}/{term.semester}"

    def get_class_group_name(self, obj):
        group = obj.course_offering.class_group
        return group.group_name if group else None

    def get_instructor_names(self, obj):
        offering = obj.course_offering
        names: list[str] = []
        if offering.instructor_id:
            profile = offering.instructor
            names.append(f"{profile.first_name} {profile.last_name}".strip())
        for profile in offering.instructors.all():
            name = f"{profile.first_name} {profile.last_name}".strip()
            if name and name not in names:
                names.append(name)
        return names

    def get_schedules(self, obj):
        return [
            {
                "weekday": schedule.weekday,
                "weekday_display": schedule.get_weekday_display(),
                "start_time": schedule.start_time.strftime("%H:%M"),
                "end_time": schedule.end_time.strftime("%H:%M"),
                "classroom": schedule.classroom,
            }
            for schedule in obj.course_offering.schedules.all()
            if schedule.status != "cancelled"
        ]


class LeaveRequestPrintSerializer(serializers.ModelSerializer):
    """Printable A4 document payload.

    `scope` is "full" for the student/admin copy and "course" for an
    instructor, whose copy only contains the offerings they teach.
    """

    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    student_program_name = serializers.SerializerMethodField()
    student_class_group_name = serializers.SerializerMethodField()
    student_year_level = serializers.IntegerField(
        source="student.academic_year_level", read_only=True
    )
    leave_type_display = serializers.CharField(
        source="get_leave_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    total_days = serializers.IntegerField(read_only=True)
    scope = serializers.SerializerMethodField()
    generated_at = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    attachments = LeaveAttachmentSerializer(many=True, read_only=True)
    requires_medical_certificate = serializers.SerializerMethodField()
    medical_certificate_attached = serializers.SerializerMethodField()

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "student_code", "student_name",
            "student_program_name", "student_class_group_name", "student_year_level",
            "leave_type", "leave_type_display",
            "start_date", "end_date", "start_time", "end_time", "total_days",
            "reason", "late_submission_reason",
            "contact_phone", "line_id", "address_during_leave",
            "guardian_acknowledged", "guardian_phone", "guardian_address",
            "status", "status_display",
            "submitted_at", "cancelled_at", "created_at",
            "scope", "generated_at", "courses",
            "attachments", "requires_medical_certificate",
            "medical_certificate_attached",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_student_program_name(self, obj):
        program = obj.student.program
        return program.program_name if program else None

    def get_student_class_group_name(self, obj):
        group = obj.student.class_group
        return group.group_name if group else None

    def get_scope(self, obj):
        return self.context.get("scope", "full")

    def get_generated_at(self, obj):
        return timezone.localtime(timezone.now()).isoformat()

    def get_requires_medical_certificate(self, obj):
        return services.requires_medical_certificate(obj)

    def get_medical_certificate_attached(self, obj):
        return any(
            attachment.attachment_type == "medical_certificate"
            for attachment in obj.attachments.all()
        )

    def get_courses(self, obj):
        courses = list(obj.courses.all())
        if self.context.get("scope") == "course":
            request = self.context.get("request")
            profile = getattr(
                getattr(request, "user", None), "instructor_profile", None
            )
            if profile is None:
                return []
            profile_id = profile.id
            courses = [
                course for course in courses
                if course.course_offering.instructor_id == profile_id
                or any(
                    instructor.id == profile_id
                    for instructor in course.course_offering.instructors.all()
                )
            ]
        return LeaveCoursePrintSerializer(courses, many=True).data


class LeaveCourseReviewWriteSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(
        choices=["reviewed", "acknowledged", "rejected"]
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")
