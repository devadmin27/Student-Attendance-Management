"""Courses, offerings, enrollments — admin manage; instructors manage their own."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import StudentProfile
from apps.courses.models import Course, CourseOffering, Enrollment
from apps.courses.serializers import (
    CourseOfferingSerializer,
    CourseSerializer,
    EnrollmentSerializer,
)
from apps.audit.models import log_audit
from common.permissions import IsAdmin, IsAdminOrInstructor, RoleRequired
from common.responses import success_response, error_response


class CourseViewSet(viewsets.ModelViewSet):
    queryset = Course.objects.all()
    serializer_class = CourseSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}  # instructors read course data
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"is_active": ["exact"]}
    search_fields = ["course_code", "course_name"]
    ordering_fields = ["course_code", "course_name", "credits"]
    ordering = ["course_code"]

    def destroy(self, request, *args, **kwargs):
        course = self.get_object()
        if course.offerings.exists():
            course.is_active = False
            course.save(update_fields=["is_active", "updated_at"])
            log_audit(request.user, "course_soft_delete", "course", course.pk, request=request)
            return success_response(
                {"id": str(course.pk), "is_active": False},
                "รายวิชานี้ถูกเปิดสอนแล้วจึงปิดใช้งานแทนการลบ",
            )
        log_audit(request.user, "course_delete", "course", course.pk, request=request)
        return super().destroy(request, *args, **kwargs)


class CourseOfferingViewSet(viewsets.ModelViewSet):
    queryset = CourseOffering.objects.select_related("course", "academic_term", "instructor", "class_group")
    serializer_class = CourseOfferingSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "course": ["exact"],
        "academic_term": ["exact"],
        "instructor": ["exact"],
        "class_group": ["exact"],
        "status": ["exact"],
    }
    search_fields = ["course__course_code", "course__course_name"]
    ordering_fields = ["course_code", "academic_year"]
    ordering = ["course__course_code"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                # Fail closed: profile-less instructor sees nothing.
                return qs.none()
            # เจ้าของหลักหรืออาจารย์ผู้รับผิดชอบร่วม
            return qs.filter(Q(instructor=profile) | Q(instructors=profile)).distinct()
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(self.request.user, "offering_create", "course_offering", instance.pk, request=self.request)

    def perform_update(self, serializer):
        instance = serializer.save()
        log_audit(self.request.user, "offering_update", "course_offering", instance.pk, request=self.request)


class EnrollmentViewSet(viewsets.ModelViewSet):
    queryset = Enrollment.objects.select_related(
        "student", "student__user", "course_offering", "course_offering__course",
        "course_offering__academic_term",
    )
    serializer_class = EnrollmentSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "student": ["exact"],
        "course_offering": ["exact"],
        "enrollment_status": ["exact"],
    }
    search_fields = ["student__student_code", "student__first_name", "student__last_name"]
    ordering_fields = ["enrolled_at", "student_code"]
    ordering = ["-enrolled_at"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                return qs.none()
            return qs.filter(
                Q(course_offering__instructor=profile) | Q(course_offering__instructors=profile)
            ).distinct()
        return qs

    def _own_offering_or_403(self, offering):
        """Instructors may only enroll into offerings they teach (primary or co-instructor)."""
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                raise PermissionDenied("บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน")
            if not offering.has_instructor(profile):
                raise PermissionDenied("คุณจัดการการลงทะเบียนได้เฉพาะรายวิชาที่คุณสอน")

    def perform_create(self, serializer):
        self._own_offering_or_403(serializer.validated_data["course_offering"])
        instance = serializer.save()
        log_audit(self.request.user, "enrollment_create", "enrollment", instance.pk, request=self.request)

    def perform_update(self, serializer):
        self._own_offering_or_403(getattr(self.instance, "course_offering", None))
        instance = serializer.save()
        log_audit(self.request.user, "enrollment_update", "enrollment", instance.pk, request=self.request)

    def perform_destroy(self, instance):
        self._own_offering_or_403(instance.course_offering)
        super().perform_destroy(instance)

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_enroll(self, request):
        """ลงทะเบียนทั้งกลุ่มเรียน: POST {course_offering, class_group}."""
        offering_id = request.data.get("course_offering")
        group_id = request.data.get("class_group")
        if not offering_id or not group_id:
            return error_response("กรุณาเลือกรายวิชาที่เปิดสอนและกลุ่มเรียน", "VALIDATION_ERROR", 400)
        try:
            offering = CourseOffering.objects.get(pk=offering_id)
        except (CourseOffering.DoesNotExist, ValueError, ValidationError):
            return error_response("ไม่พบรายวิชาที่เปิดสอนที่ระบุ", "ERROR", 400)
        try:
            students = StudentProfile.objects.filter(class_group_id=group_id, status="active")
            if not students.exists() and not request.data.get("allow_empty"):
                return error_response("ไม่พบนักศึกษาที่ใช้งานอยู่ในกลุ่มเรียนที่ระบุ", "ERROR", 400)
        except ValueError:
            return error_response("ไม่พบกลุ่มเรียนที่ระบุ", "ERROR", 400)
        self._own_offering_or_403(offering)
        if offering.status == "cancelled":
            return error_response("ไม่สามารถลงทะเบียนรายวิชาที่ถูกยกเลิกได้", "VALIDATION_ERROR", 400)

        students = StudentProfile.objects.filter(class_group_id=group_id, status="active")
        created = skipped = 0
        with transaction.atomic():
            for student in students:
                _, is_new = Enrollment.objects.get_or_create(
                    student=student, course_offering=offering,
                )
                if is_new:
                    created += 1
                else:
                    skipped += 1
        log_audit(
            request.user, "enrollment_bulk_create", "enrollment", offering.pk,
            metadata={"class_group": str(group_id), "created": created, "skipped": skipped},
            request=request,
        )
        return success_response(
            {"created": created, "skipped": skipped, "course_offering": offering_id},
            f"ลงทะเบียนเพิ่ม {created} คน (มีอยู่ก่อนแล้วข้าม {skipped} คน)",
        )
