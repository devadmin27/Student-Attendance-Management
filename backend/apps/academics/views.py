"""Academic structure CRUD — admin only (spec §3.1, §8)."""
from rest_framework import viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter

from apps.academics.models import AcademicTerm, ClassGroup, Program
from apps.academics.serializers import (
    AcademicTermSerializer,
    ClassGroupSerializer,
    ProgramSerializer,
)
from apps.audit.models import log_audit
from common.permissions import IsAdmin


class ProgramViewSet(viewsets.ModelViewSet):
    queryset = Program.objects.all()
    serializer_class = ProgramSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"is_active": ["exact"], "degree_level": ["exact"]}
    search_fields = ["program_code", "program_name"]
    ordering_fields = ["program_code", "program_name", "degree_level"]
    ordering = ["program_code"]

    def destroy(self, request, *args, **kwargs):
        program = self.get_object()
        if program.students.exists() or program.class_groups.exists():
            program.is_active = False
            program.save(update_fields=["is_active", "updated_at"])
            log_audit(request.user, "program_soft_delete", "program", program.pk, request=request)
            # Keep referential integrity: soft-delete inconsistent data.
            return self.success(program.pk, "มีข้อมูลที่ใช้งานอยู่ — ปิดใช้งานหลักสูตรแทนการลบ")
        log_audit(request.user, "program_delete", "program", program.pk, request=request)
        response = super().destroy(request, *args, **kwargs)
        return response

    def success(self, pk, message):
        from rest_framework.response import Response

        return Response({"success": True, "message": message, "data": {"id": str(pk)}})


class ClassGroupViewSet(viewsets.ModelViewSet):
    queryset = ClassGroup.objects.select_related("program")
    serializer_class = ClassGroupSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"program": ["exact"], "academic_year_level": ["exact"]}
    search_fields = ["group_code", "group_name"]
    ordering_fields = ["group_code", "group_name", "academic_year_level"]
    ordering = ["group_code"]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(self.request.user, "class_group_create", "class_group", instance.pk, request=self.request)


class AcademicTermViewSet(viewsets.ModelViewSet):
    queryset = AcademicTerm.objects.all()
    serializer_class = AcademicTermSerializer
    permission_classes = [IsAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {"is_active": ["exact"], "is_current": ["exact"]}
    search_fields = ["academic_year", "semester"]
    ordering_fields = ["academic_year", "semester", "start_date"]
    ordering = ["-academic_year", "semester"]

    def perform_create(self, serializer):
        instance = serializer.save()
        log_audit(self.request.user, "term_create", "academic_term", instance.pk, request=self.request)
