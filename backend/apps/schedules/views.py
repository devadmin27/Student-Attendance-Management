"""Class schedules: scheduling definition separate from live sessions."""
from django.db.models import Q
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.schedules.models import ClassSchedule
from apps.schedules.serializers import ClassScheduleSerializer
from common.permissions import IsAdmin, RoleRequired


class ClassScheduleViewSet(viewsets.ModelViewSet):
    queryset = ClassSchedule.objects.select_related(
        "course_offering", "course_offering__course", "course_offering__academic_term"
    )
    serializer_class = ClassScheduleSerializer
    permission_classes = [RoleRequired]
    allowed_roles = {"admin", "instructor"}
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "course_offering": ["exact"],
        "weekday": ["exact"],
        "status": ["exact"],
    }
    search_fields = ["course_offering__course__course_code", "classroom"]
    ordering_fields = ["weekday", "start_time", "end_time"]
    ordering = ["weekday", "start_time"]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                # Fail closed: profile-less instructor sees nothing.
                return qs.none()
            return qs.filter(
                Q(course_offering__instructor=profile) | Q(course_offering__instructors=profile)
            ).distinct()
        return qs

    def perform_create(self, serializer):
        self._assert_own_offering(serializer.validated_data["course_offering"])
        super().perform_create(serializer)

    def perform_update(self, serializer):
        self._assert_own_offering(
            serializer.validated_data.get("course_offering") or serializer.instance.course_offering
        )
        super().perform_update(serializer)

    def _assert_own_offering(self, offering):
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None:
                raise PermissionDenied(
                    "บัญชีนี้ยังไม่มีโปรไฟล์อาจารย์ — ให้ผู้ดูแลเพิ่มข้อมูลในหน้า Instructors ก่อน"
                )
            if not offering.has_instructor(profile):
                raise PermissionDenied("คุณจัดการตารางเรียนได้เฉพาะรายวิชาที่คุณสอน")
