"""Serializers for attendance sessions, records, check-in."""
from rest_framework import serializers

from apps.attendance.models import (
    AttendanceRecord,
    AttendanceSession,
    QRToken,
)


class AttendanceSessionSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course_offering.course.course_code", read_only=True)
    course_name = serializers.CharField(source="course_offering.course.course_name", read_only=True)
    term_label = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()
    checked_in_count = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "course_offering", "course_code", "course_name", "term_label",
            "class_schedule", "instructor", "instructor_name",
            "session_date", "check_in_start", "check_in_end",
            "late_threshold_minutes", "status", "status_display",
            "enrolled_count", "checked_in_count",
            "created_at", "updated_at", "closed_at",
        ]
        read_only_fields = [
            "id", "instructor", "status", "created_at", "updated_at", "closed_at"
        ]

    def get_term_label(self, obj):
        term = obj.course_offering.academic_term
        return f"{term.academic_year}/{term.semester}"

    def get_instructor_name(self, obj):
        if obj.instructor:
            return f"{obj.instructor.first_name} {obj.instructor.last_name}"
        return None

    def get_enrolled_count(self, obj):
        return obj.course_offering.enrollments.filter(enrollment_status="enrolled").count()

    def get_checked_in_count(self, obj):
        return obj.records.count()

    def validate(self, attrs):
        start = attrs.get("check_in_start") or getattr(self.instance, "check_in_start", None)
        end = attrs.get("check_in_end") or getattr(self.instance, "check_in_end", None)
        if start and end and end < start:
            raise serializers.ValidationError({"check_in_end": "เวลาปิดรับเช็คชื่อต้องไม่ก่อนเวลาเริ่ม"})
        return attrs


class AttendanceSessionCreateSerializer(serializers.ModelSerializer):
    """Creating the session object (Scheduled) for an upcoming class."""

    class Meta:
        model = AttendanceSession
        fields = [
            "id", "course_offering", "class_schedule",
            "session_date", "check_in_start", "check_in_end", "late_threshold_minutes",
        ]

    def validate(self, attrs):
        start = attrs.get("check_in_start", None)
        end = attrs.get("check_in_end", None)
        if start and end and end < start:
            raise serializers.ValidationError({"check_in_end": "เวลาปิดรับเช็คชื่อต้องไม่ก่อนเวลาเริ่ม"})
        return attrs

    def create(self, validated):
        # Instructor comes from the authenticated user, never client input.
        offering = validated["course_offering"]
        user = self.context["request"].user
        if offering.instructor is None and user.role != "instructor":
            raise serializers.ValidationError(
                {"course_offering": "รายวิชานี้ยังไม่มีอาจารย์ผู้รับผิดชอบ"}
            )
        if user.role == "instructor":
            # getattr with default: reverse OneToOne without a profile row
            # raises RelatedObjectDoesNotExist on direct access — map it to a
            # clear 400 instead of an unhandled 500.
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                raise serializers.ValidationError(
                    {"detail": "บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน"}
                )
            validated["instructor"] = profile
        else:
            validated["instructor"] = offering.instructor
        return super().create(validated)


class QRTokenSerializer(serializers.ModelSerializer):
    expires_in_seconds = serializers.SerializerMethodField()

    class Meta:
        model = QRToken
        fields = ["id", "expires_at", "expires_in_seconds", "issued_at", "use_count"]
        read_only_fields = fields

    def get_expires_in_seconds(self, token):
        from django.utils import timezone

        delta = (token.expires_at - timezone.now()).total_seconds()
        return max(0, int(delta))


class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source="attendance_session.course_offering.course.course_code", read_only=True)
    session_date = serializers.DateField(source="attendance_session.session_date", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    method_display = serializers.CharField(source="get_check_in_method_display", read_only=True)
    edited_by_username = serializers.CharField(source="edited_by.username", read_only=True, default=None)

    class Meta:
        model = AttendanceRecord
        fields = [
            "id", "attendance_session", "session_date", "course_code",
            "student", "student_code", "student_name",
            "status", "status_display", "checked_in_at",
            "check_in_method", "method_display",
            "edited_by_username", "edit_reason",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "student", "attendance_session", "checked_in_at",
            "check_in_method", "edited_by", "created_at", "updated_at",
        ]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"


class AttendanceRecordUpdateSerializer(serializers.ModelSerializer):
    """Instructor/admin edit of status with mandatory reason (audited)."""

    class Meta:
        model = AttendanceRecord
        fields = ["status", "edit_reason"]

    def validate(self, attrs):
        status = attrs.get("status")
        reason = (attrs.get("edit_reason") or "").strip()
        if reason == "":
            raise serializers.ValidationError({"edit_reason": "กรุณาระบุเหตุผลการแก้ไข"})
        statuses = {c[0] for c in AttendanceRecord._meta.get_field("status").choices}
        if status and status not in statuses:
            raise serializers.ValidationError({"status": "สถานะไม่ถูกต้อง"})
        return attrs


class CheckInSerializer(serializers.Serializer):
    """Body for POST /attendance/check-in/ — only the scanned token; nothing
    else trusted from the client (spec §10.2: session id/status are not taken
    from client)."""

    token = serializers.CharField(write_only=True, max_length=256)


class CheckInResultSerializer(serializers.Serializer):
    attendance_session = serializers.CharField()
    course_code = serializers.CharField()
    course_name = serializers.CharField()
    session_date = serializers.DateField()
    status = serializers.CharField()
    checked_in_at = serializers.DateTimeField()


class SessionRosterSerializer(serializers.Serializer):
    """Per-session roster rows (enrolled student + their check-in state)."""

    id = serializers.CharField(read_only=True)
    student_code = serializers.CharField(read_only=True)
    student_name = serializers.CharField(read_only=True)
    checked_in_status = serializers.CharField(read_only=True, allow_null=True)
    checked_in_at = serializers.DateTimeField(read_only=True, allow_null=True)
