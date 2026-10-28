"""Class schedules: scheduling definition separate from live sessions."""
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.schedules.models import ClassSchedule
from apps.schedules.serializers import ClassScheduleSerializer
from common.permissions import IsAdmin, RoleRequired


class ClassScheduleViewSet(viewsets.ModelViewSet):
    queryset = ClassSchedule.objects.select_related("course_offering", "course_offering__course")
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
