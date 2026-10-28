"""Courses, offerings, enrollments — admin manage; instructors read own."""
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.courses.models import Course, CourseOffering, Enrollment
from apps.courses.serializers import (
    CourseOfferingSerializer,
    CourseSerializer,
    EnrollmentSerializer,
)
from apps.audit.models import log_audit
from common.permissions import IsAdmin, IsAdminOrInstructor, RoleRequired
from common.responses import success_response


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
        if user.role == "instructor" and getattr(user, "instructor_profile", None):
            # Ownership scope: instructors only see their own offerings.
            return qs.filter(instructor=user.instructor_profile)
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
        if user.role == "instructor" and getattr(user, "instructor_profile", None):
            return qs.filter(course_offering__instructor=user.instructor_profile)
        return qs

    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(self.request.user, "enrollment_create", "enrollment", instance.pk, request=self.request)
