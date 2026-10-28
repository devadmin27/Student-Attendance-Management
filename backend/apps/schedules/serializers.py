"""Serializers for class schedules."""
from datetime import timedelta

from rest_framework import serializers

from apps.schedules.models import ClassSchedule


class ClassScheduleSerializer(serializers.ModelSerializer):
    course_code = serializers.CharField(source="course_offering.course.course_code", read_only=True)
    course_name = serializers.CharField(source="course_offering.course.course_name", read_only=True)
    term_label = serializers.SerializerMethodField()
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = ClassSchedule
        fields = [
            "id", "course_offering", "course_code", "course_name", "term_label",
            "weekday", "weekday_display", "start_time", "end_time",
            "classroom", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_term_label(self, obj):
        term = obj.course_offering.academic_term
        return f"{term.academic_year}/{term.semester}"

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น"})
        if start is not None and end is not None and (
            isinstance(start, str) or isinstance(end, str)
        ):
            pass
        return attrs
