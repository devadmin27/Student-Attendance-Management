"""Student leave APIs, instructor course inbox, and admin read-only access.

RBAC is enforced here (and in the service layer), never by the SPA alone.
"""
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.dateparse import parse_date, parse_time
from rest_framework import status, viewsets
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.views import APIView

from apps.audit.models import log_audit
from apps.leaves import services
from apps.leaves.models import LeaveAttachment, LeaveCourse, LeaveRequest
from apps.leaves.serializers import (
    LeaveAttachmentSerializer,
    LeaveAttachmentWriteSerializer,
    LeaveCourseInboxSerializer,
    LeaveCourseReviewWriteSerializer,
    LeaveRequestPrintSerializer,
    LeaveRequestSerializer,
    LeaveRequestWriteSerializer,
)
from common.permissions import RoleRequired
from common.responses import error_response, success_response


class LeaveRequestViewSet(viewsets.GenericViewSet):
    """Students own their requests; admins may read all requests."""

    permission_classes = [RoleRequired]
    allowed_roles = {"student", "admin"}
    serializer_class = LeaveRequestSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "status": ["exact"],
        "leave_type": ["exact"],
        "student": ["exact"],
        "start_date": ["gte", "lte"],
        "end_date": ["gte", "lte"],
    }
    search_fields = [
        "student__student_code", "student__first_name", "student__last_name",
    ]
    ordering_fields = ["created_at", "start_date", "submitted_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LeaveRequest.objects.none()
        qs = LeaveRequest.objects.select_related(
            "student", "student__program", "student__class_group"
        ).prefetch_related(
            "courses",
            "courses__course_offering__course",
            "courses__course_offering__academic_term",
            "courses__course_offering__class_group",
            "courses__course_offering__schedules",
            "courses__reviews",
            "courses__reviews__reviewer",
            "courses__reviews__reviewer__instructor_profile",
            "courses__reviewed_by",
            "courses__reviewed_by__instructor_profile",
            "attachments",
        )
        user = self.request.user
        if user.role == "admin":
            return qs
        profile = getattr(user, "student_profile", None)
        if profile is None:
            return qs.none()
        return qs.filter(student=profile)

    # -- CRUD ---------------------------------------------------------------
    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = LeaveRequestSerializer(
            page if page is not None else queryset, many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return success_response(serializer.data, "โหลดรายการคำร้องลาสำเร็จ")

    def retrieve(self, request, pk=None):
        instance = self.get_object()
        serializer = LeaveRequestSerializer(instance, context={"request": request})
        return success_response(serializer.data, "โหลดคำร้องลาสำเร็จ")

    def _write_student_only(self, request):
        if request.user.role != "student":
            return error_response(
                "ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        return None

    def create(self, request):
        denied = self._write_student_only(request)
        if denied:
            return denied
        serializer = LeaveRequestWriteSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        log_audit(
            request.user, "leave_create", "leave_request", instance.pk,
            metadata={"course_count": instance.courses.count()}, request=request,
        )
        data = LeaveRequestSerializer(instance, context={"request": request}).data
        return success_response(data, "บันทึกร่างคำร้องลาสำเร็จ", status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        denied = self._write_student_only(request)
        if denied:
            return denied
        instance = self.get_object()
        if not instance.is_editable:
            return error_response(
                "แก้ไขได้เฉพาะคำร้องที่เป็นแบบร่าง", "LEAVE_NOT_EDITABLE",
                status.HTTP_400_BAD_REQUEST,
            )
        serializer = LeaveRequestWriteSerializer(
            instance, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        instance = serializer.save()
        log_audit(
            request.user, "leave_update", "leave_request", instance.pk,
            metadata={"course_count": instance.courses.count()}, request=request,
        )
        data = LeaveRequestSerializer(instance, context={"request": request}).data
        return success_response(data, "แก้ไขคำร้องลาสำเร็จ")

    def partial_update(self, request, pk=None):
        return self.update(request, pk=pk)

    # -- Actions ------------------------------------------------------------
    @action(detail=True, methods=["post"], url_path="submit")
    def submit(self, request, pk=None):
        instance = self.get_object()
        if request.user.role != "student":
            return error_response(
                "ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        services.submit_leave_request(instance)
        log_audit(
            request.user, "leave_submit", "leave_request", instance.pk,
            metadata={"course_count": instance.courses.count()}, request=request,
        )
        data = LeaveRequestSerializer(instance, context={"request": request}).data
        return success_response(data, "ส่งคำร้องลาสำเร็จ")

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        instance = self.get_object()
        if request.user.role != "student":
            return error_response(
                "ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        old_status = instance.status
        services.cancel_leave_request(instance)
        log_audit(
            request.user, "leave_cancel", "leave_request", instance.pk,
            metadata={"from": old_status, "to": instance.status}, request=request,
        )
        data = LeaveRequestSerializer(instance, context={"request": request}).data
        return success_response(data, "ยกเลิกคำร้องลาสำเร็จ")

    @action(detail=True, methods=["get", "post"], url_path="attachments")
    def attachments(self, request, pk=None):
        """List (owner/admin) or upload (owner, draft only) attachments."""
        instance = self.get_object()
        if request.method.lower() == "get":
            serializer = LeaveAttachmentSerializer(
                instance.attachments.all(), many=True
            )
            return success_response(serializer.data, "โหลดไฟล์แนบสำเร็จ")

        if request.user.role != "student":
            return error_response(
                "ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        serializer = LeaveAttachmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attachment = services.create_leave_attachment(
            instance,
            serializer.validated_data["file"],
            serializer.validated_data["attachment_type"],
            request.user,
        )
        log_audit(
            request.user, "leave_attachment_upload", "leave_attachment",
            attachment.pk,
            metadata={
                "leave_request": str(instance.pk),
                "attachment_type": attachment.attachment_type,
                "size": attachment.size,
            },
            request=request,
        )
        return success_response(
            LeaveAttachmentSerializer(attachment).data,
            "แนบไฟล์สำเร็จ",
            status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path=r"attachments/(?P<attachment_id>[^/.]+)",
    )
    def delete_attachment(self, request, pk=None, attachment_id=None):
        if request.user.role != "student":
            return error_response(
                "ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        attachment = get_object_or_404(
            instance.attachments.all(), pk=attachment_id
        )
        services.delete_leave_attachment(instance, attachment)
        log_audit(
            request.user, "leave_attachment_delete", "leave_attachment",
            attachment_id,
            metadata={"leave_request": str(instance.pk)}, request=request,
        )
        return success_response(None, "ลบไฟล์แนบสำเร็จ")

    @action(detail=False, methods=["get"], url_path="available-courses")
    def available_courses(self, request):
        if request.user.role != "student":
            return error_response(
                "เฉพาะนักศึกษาเท่านั้น", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        profile = getattr(request.user, "student_profile", None)
        if profile is None:
            return error_response(
                "บัญชีนี้ยังไม่มีโปรไฟล์นักศึกษา", "NO_STUDENT_PROFILE",
                status.HTTP_400_BAD_REQUEST,
            )
        start_date = parse_date(request.query_params.get("start_date", ""))
        end_date = parse_date(request.query_params.get("end_date", ""))
        if start_date is None or end_date is None:
            return error_response(
                "ต้องระบุ start_date และ end_date (YYYY-MM-DD)",
                "INVALID_DATE_RANGE", status.HTTP_400_BAD_REQUEST,
            )
        start_time = parse_time(request.query_params.get("start_time", ""))
        end_time = parse_time(request.query_params.get("end_time", ""))
        data = services.available_courses(
            profile, start_date, end_date, start_time, end_time
        )
        return success_response(data, "โหลดรายวิชาที่เกี่ยวข้องสำเร็จ")


class LeaveCourseViewSet(viewsets.GenericViewSet):
    """Instructor course inbox (own offerings only) and admin read-only view."""

    permission_classes = [RoleRequired]
    allowed_roles = {"instructor", "admin"}
    serializer_class = LeaveCourseInboxSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = {
        "review_status": ["exact"],
        "course_offering": ["exact"],
        "leave_request": ["exact"],
        "leave_request__status": ["exact"],
        "leave_request__student": ["exact"],
        "leave_request__start_date": ["gte", "lte"],
    }
    search_fields = [
        "leave_request__student__student_code",
        "leave_request__student__first_name",
        "leave_request__student__last_name",
        "course_offering__course__course_code",
        "course_offering__course__course_name",
    ]
    ordering_fields = ["created_at", "reviewed_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return LeaveCourse.objects.none()
        qs = LeaveCourse.objects.select_related(
            "leave_request",
            "leave_request__student",
            "course_offering",
            "course_offering__course",
            "course_offering__academic_term",
            "course_offering__class_group",
            "course_offering__instructor",
            "reviewed_by",
            "reviewed_by__instructor_profile",
        ).prefetch_related(
            "reviews", "reviews__reviewer",
            "reviews__reviewer__instructor_profile",
            "course_offering__instructors",
            "leave_request__attachments",
        )
        user = self.request.user
        if user.role == "admin":
            return qs
        profile = getattr(user, "instructor_profile", None)
        if profile is None:
            return qs.none()
        return qs.exclude(
            leave_request__status="draft"
        ).filter(
            Q(course_offering__instructor=profile)
            | Q(course_offering__instructors=profile)
        ).distinct()

    def list(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = LeaveCourseInboxSerializer(
            page if page is not None else queryset, many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return success_response(serializer.data, "โหลดคำร้องลารายวิชาสำเร็จ")

    def retrieve(self, request, pk=None):
        instance = self.get_object()
        serializer = LeaveCourseInboxSerializer(
            instance, context={"request": request}
        )
        return success_response(serializer.data, "โหลดคำร้องลารายวิชาสำเร็จ")

    @action(detail=True, methods=["post"], url_path="review")
    def review(self, request, pk=None):
        if request.user.role != "instructor":
            return error_response(
                "เฉพาะอาจารย์ผู้สอนรายวิชาเท่านั้น", "PERMISSION_DENIED",
                status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        serializer = LeaveCourseReviewWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        review = services.review_course(
            instance,
            request.user,
            serializer.validated_data["review_status"],
            serializer.validated_data.get("comment", ""),
        )
        log_audit(
            request.user, "leave_course_review", "leave_course", instance.pk,
            metadata={
                "review_status": review.review_status,
                "leave_request": str(instance.leave_request_id),
            },
            request=request,
        )
        instance = self.get_queryset().get(pk=instance.pk)
        data = LeaveCourseInboxSerializer(
            instance, context={"request": request}
        ).data
        return success_response(data, "บันทึกผลการพิจารณารายวิชาสำเร็จ")


class LeaveRequestPrintView(APIView):
    """Read-only A4 document data for students, instructors, and admins.

    Students may print only their own request, admins may print any request,
    and instructors may print requests that include an offering they teach
    (drafts stay hidden). An instructor's payload is scoped to their own
    courses so other instructors' comments are never exposed.
    """

    permission_classes = [RoleRequired]
    allowed_roles = {"student", "instructor", "admin"}

    def get(self, request, pk):
        queryset = LeaveRequest.objects.select_related(
            "student", "student__program", "student__class_group"
        ).prefetch_related(
            "courses",
            "courses__course_offering__course",
            "courses__course_offering__academic_term",
            "courses__course_offering__class_group",
            "courses__course_offering__instructor",
            "courses__course_offering__instructors",
            "courses__course_offering__schedules",
            "courses__reviews",
            "courses__reviews__reviewer",
            "courses__reviews__reviewer__instructor_profile",
            "attachments",
        )
        role = request.user.role
        if role == "admin":
            instance = get_object_or_404(queryset, pk=pk)
            scope = "full"
        elif role == "student":
            profile = getattr(request.user, "student_profile", None)
            if profile is None:
                raise Http404
            instance = get_object_or_404(queryset, pk=pk, student=profile)
            scope = "full"
        else:
            profile = getattr(request.user, "instructor_profile", None)
            if profile is None:
                raise Http404
            instance = get_object_or_404(
                queryset.exclude(status="draft")
                .filter(
                    Q(courses__course_offering__instructor=profile)
                    | Q(courses__course_offering__instructors=profile)
                )
                .distinct(),
                pk=pk,
            )
            scope = "course"

        serializer = LeaveRequestPrintSerializer(
            instance, context={"request": request, "scope": scope}
        )
        return success_response(serializer.data, "โหลดเอกสารใบลาสำเร็จ")


class LeavePolicyView(APIView):
    """Current submission policy, so the SPA never hardcodes college rules."""

    permission_classes = [RoleRequired]
    allowed_roles = {"student", "instructor", "admin"}

    def get(self, request):
        return success_response(services.leave_policy(), "โหลดนโยบายการลาสำเร็จ")


class LeaveAttachmentDownloadView(APIView):
    """Authenticated download with the same role scoping as the request.

    Students may download their own files, admins any file, and instructors
    only files on submitted requests that include one of their courses.
    """

    permission_classes = [RoleRequired]
    allowed_roles = {"student", "instructor", "admin"}

    def get(self, request, pk, attachment_id):
        queryset = LeaveAttachment.objects.select_related("leave_request")
        role = request.user.role
        if role == "student":
            profile = getattr(request.user, "student_profile", None)
            if profile is None:
                raise Http404
            queryset = queryset.filter(leave_request__student=profile)
        elif role == "instructor":
            profile = getattr(request.user, "instructor_profile", None)
            if profile is None:
                raise Http404
            queryset = (
                queryset.exclude(leave_request__status="draft")
                .filter(
                    Q(leave_request__courses__course_offering__instructor=profile)
                    | Q(
                        leave_request__courses__course_offering__instructors=profile
                    )
                )
                .distinct()
            )

        attachment = get_object_or_404(
            queryset, pk=attachment_id, leave_request_id=pk
        )
        try:
            file_handle = attachment.file.open("rb")
        except FileNotFoundError:
            raise Http404

        response = FileResponse(
            file_handle,
            as_attachment=True,
            filename=attachment.original_name,
        )
        if attachment.content_type:
            response["Content-Type"] = attachment.content_type
        return response
