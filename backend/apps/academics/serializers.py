"""Serializers for academic structure."""
from rest_framework import serializers

from apps.academics.models import AcademicTerm, ClassGroup, Program


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = [
            "id", "program_code", "program_name", "degree_level",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ClassGroupSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source="program.program_name", read_only=True)

    class Meta:
        model = ClassGroup
        fields = [
            "id", "group_code", "group_name", "program", "program_name",
            "academic_year_level", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AcademicTermSerializer(serializers.ModelSerializer):
    semester_display = serializers.CharField(source="get_semester_display", read_only=True)

    class Meta:
        model = AcademicTerm
        fields = [
            "id", "academic_year", "semester", "semester_display",
            "start_date", "end_date", "is_active", "is_current",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "วันสิ้นสุดต้องไม่ก่อนวันเริ่มต้น"})
        year = attrs.get("academic_year", getattr(self.instance, "academic_year", None))
        if year is not None and not (2_400 <= year <= 3_000):
            # Thai Buddhist-calendar school year sanity (พ.ศ.)
            raise serializers.ValidationError({"academic_year": "ปีการศึกษาต้องเป็นปี พ.ศ. ที่ถูกต้อง"})
        return attrs

    def create(self, validated):
        # Ensure only one "current" term by unflagging others atomically.
        if validated.get("is_current"):
            AcademicTerm.objects.filter(is_current=True).update(is_current=False)
        return super().create(validated)

    def update(self, instance, validated):
        if validated.get("is_current"):
            AcademicTerm.objects.exclude(pk=instance.pk).filter(is_current=True).update(is_current=False)
        return super().update(instance, validated)
