"""Serializers for leave requests, available courses, and course reviews."""
from django.db import transaction
from rest_framework import serializers

from apps.leaves import services
from apps.leaves.models import LeaveCourse, LeaveCourseReview, LeaveRequest


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


class LeaveRequestSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    leave_type_display = serializers.CharField(
        source="get_leave_type_display", read_only=True
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    courses = LeaveCourseSerializer(many=True, read_only=True)
    course_count = serializers.IntegerField(source="courses.count", read_only=True)
    is_editable = serializers.BooleanField(read_only=True)
    is_cancellable = serializers.BooleanField(read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id", "student", "student_code", "student_name",
            "leave_type", "leave_type_display",
            "start_date", "end_date", "start_time", "end_time",
            "reason", "status", "status_display",
            "submitted_at", "cancelled_at",
            "course_count", "courses", "is_editable", "is_cancellable",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()


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
            "reason", "course_offering_ids",
        ]

    def validate(self, attrs):
        start_date = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end_date = attrs.get("end_date", getattr(self.instance, "end_date", None))
        start_time = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end_time = attrs.get("end_time", getattr(self.instance, "end_time", None))
        services.validate_leave_range(start_date, end_date, start_time, end_time)
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
    submitted_at = serializers.DateTimeField(
        source="leave_request.submitted_at", read_only=True, allow_null=True
    )
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
            "submitted_at", "course_offering", "course_code", "course_name",
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


class LeaveCourseReviewWriteSerializer(serializers.Serializer):
    review_status = serializers.ChoiceField(
        choices=["reviewed", "acknowledged", "rejected"]
    )
    comment = serializers.CharField(required=False, allow_blank=True, default="")
