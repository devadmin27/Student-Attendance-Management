"""Serializers for courses, offerings, enrollments."""
from rest_framework import serializers

from apps.courses.models import Course, CourseOffering, Enrollment


class CourseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Course
        fields = [
            "id", "course_code", "course_name", "credits", "description",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_credits(self, value):
        if value <= 0 or value > 12:
            raise serializers.ValidationError("หน่วยกิตต้องอยู่ระหว่าง 0.5-12")
        return value


class CourseOfferingSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course.course_code", read_only=True)
    course_name = serializers.CharField(source="course.course_name", read_only=True)
    term_label = serializers.SerializerMethodField()
    instructor_name = serializers.SerializerMethodField()
    enrollment_count = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = [
            "id", "course", "course_code", "course_name",
            "academic_term", "term_label",
            "instructor", "instructor_name", "class_group",
            "status", "enrollment_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_term_label(self, obj):
        return f"{obj.academic_term.academic_year}/{obj.academic_term.semester}"

    def get_instructor_name(self, obj):
        if obj.instructor:
            return f"{obj.instructor.first_name} {obj.instructor.last_name}"
        return None

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(enrollment_status="enrolled").count()


class EnrollmentSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source="course_offering.course.course_code", read_only=True)
    course_name = serializers.CharField(source="course_offering.course.course_name", read_only=True)

    class Meta:
        model = Enrollment
        fields = [
            "id", "student", "student_code", "student_name",
            "course_offering", "course_code", "course_name",
            "enrollment_status", "enrolled_at",
        ]
        read_only_fields = ["id", "enrolled_at"]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def validate(self, attrs):
        student = attrs.get("student") or getattr(self.instance, "student", None)
        offering = attrs.get("course_offering") or getattr(self.instance, "course_offering", None)
        if student and offering:
            if offering.status == "cancelled":
                raise serializers.ValidationError({"course_offering": "ไม่สามารถลงทะเบียนรายวิชาที่ถูกยกเลิกได้"})
            if self.instance is None:
                duplicate = Enrollment.objects.filter(
                    student=student,
                    course_offering__course=offering.course,
                    course_offering__academic_term=offering.academic_term,
                    enrollment_status="enrolled",
                ).exists()
                if duplicate:
                    raise serializers.ValidationError(
                        {"course_offering": "นักศึกษาลงทะเบียนรายวิชานี้ในภาคการศึกษาเดียวกันแล้ว"}
                    )
        return attrs
