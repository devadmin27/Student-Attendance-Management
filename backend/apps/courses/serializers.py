"""Serializers for courses, offerings, enrollments."""
from rest_framework import serializers

from apps.accounts.models import InstructorProfile
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
    # อาจารย์ผู้รับผิดชอบ — เลือกได้หลายคน (คนแรกจะถูก sync เป็นอาจารย์หลัก)
    instructors = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=InstructorProfile.objects.all(),
    )
    instructor_ids = serializers.SerializerMethodField()
    instructor_names = serializers.SerializerMethodField()

    class Meta:
        model = CourseOffering
        fields = [
            "id", "course", "course_code", "course_name",
            "academic_term", "term_label",
            "instructor", "instructor_name", "instructors", "instructor_ids", "instructor_names",
            "class_group",
            "status", "enrollment_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "instructor", "created_at", "updated_at"]

    def get_term_label(self, obj):
        return f"{obj.academic_term.academic_year}/{obj.academic_term.semester}"

    def get_instructor_name(self, obj):
        if obj.instructor:
            return f"{obj.instructor.first_name} {obj.instructor.last_name}"
        return None

    def get_instructor_ids(self, obj):
        return [str(pk) for pk in obj.instructors.values_list("pk", flat=True)]

    def get_instructor_names(self, obj):
        if obj.instructor and obj.instructor_id:
            names = [f"{obj.instructor.first_name} {obj.instructor.last_name}"]
        else:
            names = []
        for p in obj.instructors.exclude(pk=obj.instructor_id):
            names.append(f"{p.first_name} {p.last_name}")
        return names

    def _chosen_instructors(self, validated):
        return list(validated.get("instructors") or [])

    def create(self, validated):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        chosen = self._chosen_instructors(validated)
        if user is not None and user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                raise serializers.ValidationError(
                    {"detail": "บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน"}
                )
            if profile not in chosen:
                chosen = [profile] + chosen
            validated["instructor"] = profile
            validated["instructors"] = chosen
        elif validated.get("instructors"):
            # Admin: อาจารย์หลัก = คนแรกในรายการ (ถ้าไม่ได้ระบุ FK เอาไว้)
            if not validated.get("instructor"):
                validated["instructor"] = chosen[0]
        instance = super().create(validated)
        if not instance.instructor_id and instance.instructors.exists():
            instance.instructor = instance.instructors.first()
            instance.save(update_fields=["instructor"])
        return instance

    def update(self, instance, validated):
        user = getattr(self.context.get("request"), "user", None)
        if "instructors" in validated and user is not None and user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                raise serializers.ValidationError(
                    {"detail": "บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน"}
                )
            chosen = self._chosen_instructors(validated)
            if profile not in chosen:
                chosen = [profile] + chosen
            validated["instructors"] = chosen
        chosen = self._chosen_instructors(validated)
        instance = super().update(instance, validated)
        if "instructors" in validated:
            # อาจารย์หลักต้องยังอยู่ในรายการที่เลือก; ถ้าไม่ใช่ ตั้งเป็นคนแรกของรายการใหม่
            if chosen:
                if instance.instructor_id not in {p.id for p in chosen}:
                    instance.instructor = chosen[0]
                    instance.save(update_fields=["instructor"])
            else:
                instance.instructor = None
                instance.save(update_fields=["instructor"])
        return instance

    def get_enrollment_count(self, obj):
        return obj.enrollments.filter(enrollment_status="enrolled").count()


class EnrollmentSerializer(serializers.ModelSerializer):
    student_code = serializers.CharField(source="student.student_code", read_only=True)
    student_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source="course_offering.course.course_code", read_only=True)
    course_name = serializers.CharField(source="course_offering.course.course_name", read_only=True)
    attendance_record_count = serializers.SerializerMethodField()

    class Meta:
        model = Enrollment
        fields = [
            "id", "student", "student_code", "student_name",
            "course_offering", "course_code", "course_name",
            "enrollment_status", "enrolled_at", "attendance_record_count",
        ]
        read_only_fields = ["id", "enrolled_at"]

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}"

    def get_attendance_record_count(self, obj):
        # The list queryset annotates this; create/update responses fall back
        # to a single count query so every payload has the same shape.
        annotated = getattr(obj, "attendance_record_count", None)
        if annotated is not None:
            return annotated
        return obj.student.attendance_records.filter(
            attendance_session__course_offering_id=obj.course_offering_id
        ).count()

    def validate(self, attrs):
        student = attrs.get("student") or getattr(self.instance, "student", None)
        offering = attrs.get("course_offering") or getattr(self.instance, "course_offering", None)
        if student and offering:
            offering_changed = (
                self.instance is None or offering.pk != self.instance.course_offering_id
            )
            if offering_changed and offering.status in {"cancelled", "completed"}:
                reason = (
                    "ถูกยกเลิก" if offering.status == "cancelled" else "จบภาคเรียนแล้ว"
                )
                raise serializers.ValidationError(
                    {"course_offering": f"ไม่สามารถลงทะเบียนรายวิชาที่{reason}ได้"}
                )
            if self.instance is not None:
                student_changed = student.pk != self.instance.student_id
                if (student_changed or offering_changed) and self.instance.student.attendance_records.filter(
                    attendance_session__course_offering_id=self.instance.course_offering_id
                ).exists():
                    raise serializers.ValidationError(
                        "มีประวัติเช็คชื่อในรายวิชานี้แล้ว — ไม่สามารถเปลี่ยนนักศึกษาหรือรายวิชาได้ "
                        "ให้ถอนการลงทะเบียนแล้วลงทะเบียนใหม่แทน"
                    )
            target_status = (
                attrs.get("enrollment_status")
                or getattr(self.instance, "enrollment_status", None)
                or "enrolled"
            )
            if target_status == "enrolled":
                reinstating = (
                    self.instance is None or self.instance.enrollment_status != "enrolled"
                )
                if reinstating and offering.status in {"cancelled", "completed"}:
                    raise serializers.ValidationError(
                        {"course_offering": "ไม่สามารถลงทะเบียนรายวิชาที่ปิดรับลงทะเบียนแล้วได้"}
                    )
                duplicate = Enrollment.objects.filter(
                    student=student,
                    course_offering__course=offering.course,
                    course_offering__academic_term=offering.academic_term,
                    enrollment_status="enrolled",
                )
                if self.instance is not None:
                    duplicate = duplicate.exclude(pk=self.instance.pk)
                if duplicate.exists():
                    raise serializers.ValidationError(
                        {"course_offering": "นักศึกษาลงทะเบียนรายวิชานี้ในภาคการศึกษาเดียวกันแล้ว"}
                    )
        return attrs
