"""Courses, offerings, enrollments — admin manage; instructors manage their own."""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, F, Q
from uuid import UUID
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

    def perform_destroy(self, instance):
        """ลบการเปิดสอน: อาจารย์ลบได้เฉพาะของตน; ถ้ามีข้อมูลผูก (PROTECT)
        ให้ปิดสถานะเป็นยกเลิกแทนการลบจริง เพื่อรักษาความถูกต้องอ้างอิง"""
        user = self.request.user
        if user.role == "instructor":
            profile = getattr(user, "instructor_profile", None)
            if profile is None or not instance.has_instructor(profile):
                raise PermissionDenied("คุณลบการเปิดสอนได้เฉพาะรายวิชาที่คุณสอน")
        busy = instance.enrollments.exists() or instance.attendance_sessions.exists()
        if busy:
            if instance.status != "cancelled":
                instance.status = "cancelled"
                instance.save(update_fields=["status", "updated_at"])
            log_audit(
                user, "offering_soft_delete", "course_offering", instance.pk, request=self.request
            )
            return
        log_audit(user, "offering_delete", "course_offering", instance.pk, request=self.request)
        super().perform_destroy(instance)


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
    MAX_BATCH = 200

    def get_queryset(self):
        qs = super().get_queryset().annotate(
            attendance_record_count=Count(
                "student__attendance_records",
                filter=Q(
                    student__attendance_records__attendance_session__course_offering_id=F(
                        "course_offering_id"
                    )
                ),
                distinct=True,
            )
        )
        # Optional term filter for finding past-term enrollments (e.g. a course
        # that has already finished) — FK filter params go through UUID casts.
        term_id = self.request.query_params.get("academic_term")
        if term_id:
            try:
                UUID(str(term_id))
            except (TypeError, ValueError):
                return qs.none()
            qs = qs.filter(course_offering__academic_term_id=term_id)
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

    def _record_count(self, instance):
        """Attendance history for this student within this offering."""
        return instance.student.attendance_records.filter(
            attendance_session__course_offering_id=instance.course_offering_id
        ).count()

    def _enrollment_meta(self, instance):
        return {
            "student_code": instance.student.student_code,
            "course_code": instance.course_offering.course.course_code,
            "offering_id": str(instance.course_offering_id),
        }

    def destroy(self, request, *args, **kwargs):
        """Hard-delete only when the student has no attendance history.

        Enrollment rows can be deleted independently of attendance records
        (there is no FK), so deleting a used enrollment would silently detach
        the student's check-in history. Withdrawing keeps the row/status and is
        the correct operation once a course has started.
        """
        instance = self.get_object()
        self._own_offering_or_403(instance.course_offering)
        record_count = self._record_count(instance)
        if record_count:
            return error_response(
                f"นักศึกษามีประวัติเช็คชื่อ {record_count} ครั้งในรายวิชานี้ — "
                "ใช้ \"ถอนการลงทะเบียน\" เพื่อเก็บประวัติแทนการลบ",
                "HAS_ATTENDANCE",
                status.HTTP_409_CONFLICT,
            )
        resource_id = instance.pk
        metadata = self._enrollment_meta(instance)
        super().destroy(request, *args, **kwargs)
        log_audit(
            request.user, "enrollment_delete", "enrollment", resource_id,
            metadata=metadata, request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _batch_ids(self, request):
        """Validate a batch id list; returns (ids, error_response)."""
        raw_ids = request.data.get("ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return None, error_response(
                "กรุณาเลือกรายการอย่างน้อย 1 รายการ",
                "INVALID_IDS",
                status.HTTP_400_BAD_REQUEST,
            )
        if len(raw_ids) > self.MAX_BATCH:
            return None, error_response(
                f"เลือกได้ครั้งละไม่เกิน {self.MAX_BATCH} รายการ",
                "BATCH_TOO_LARGE",
                status.HTTP_400_BAD_REQUEST,
            )
        ids = []
        for raw in raw_ids:
            try:
                ids.append(UUID(str(raw)))
            except (TypeError, ValueError):
                return None, error_response(
                    "มีรหัสรายการที่ไม่ถูกต้อง",
                    "INVALID_IDS",
                    status.HTTP_400_BAD_REQUEST,
                )
        # Deduplicate while keeping the caller's order.
        return list(dict.fromkeys(ids)), None

    def _batch_result(self, instance, *, ok, skipped=False, code="", message=""):
        return {
            "id": str(instance.pk),
            "student_code": instance.student.student_code,
            "course_code": instance.course_offering.course.course_code,
            "ok": ok,
            "skipped": skipped,
            "code": code,
            "message": message,
        }

    def _batch_data(self, ids, results, succeeded, skipped):
        failed = len(results) - succeeded - skipped
        return {
            "requested": len(ids),
            "succeeded": succeeded,
            "skipped": skipped,
            "failed": failed,
            "results": results,
        }

    @action(detail=False, methods=["post"], url_path="batch-withdraw")
    def batch_withdraw(self, request):
        """Withdraw many enrollments — keeps every attendance record.

        Each row is handled independently: already-dropped rows are reported as
        skipped and completed rows as failed, so one bad row never cancels the
        rest of the batch.
        """
        ids, error = self._batch_ids(request)
        if error:
            return error
        reason = str(request.data.get("reason", "")).strip()[:500]
        if not reason:
            return error_response(
                "กรุณาระบุเหตุผลการถอนการลงทะเบียน",
                "REASON_REQUIRED",
                status.HTTP_400_BAD_REQUEST,
            )
        scoped = {obj.pk: obj for obj in self.get_queryset().filter(pk__in=ids)}
        results = []
        succeeded = skipped = 0
        for pk in ids:
            instance = scoped.get(pk)
            if instance is None:
                results.append(
                    {
                        "id": str(pk),
                        "student_code": "",
                        "course_code": "",
                        "ok": False,
                        "skipped": False,
                        "code": "NOT_FOUND",
                        "message": "ไม่พบรายการหรือไม่มีสิทธิ์จัดการ",
                    }
                )
                continue
            if instance.enrollment_status == "completed":
                results.append(
                    self._batch_result(
                        instance, ok=False, code="INVALID_STATUS",
                        message="จบรายวิชาแล้ว — ไม่สามารถถอนการลงทะเบียนได้",
                    )
                )
                continue
            if instance.enrollment_status == "dropped":
                skipped += 1
                results.append(
                    self._batch_result(
                        instance, ok=True, skipped=True,
                        message="ถอนการลงทะเบียนอยู่แล้ว",
                    )
                )
                continue
            with transaction.atomic():
                instance.enrollment_status = "dropped"
                instance.save(update_fields=["enrollment_status", "updated_at"])
                log_audit(
                    request.user, "enrollment_withdraw", "enrollment", instance.pk,
                    metadata={
                        **self._enrollment_meta(instance),
                        "reason": reason,
                        "batch": True,
                        "batch_size": len(ids),
                    },
                    request=request,
                )
            succeeded += 1
            results.append(self._batch_result(instance, ok=True))
        data = self._batch_data(ids, results, succeeded, skipped)
        message = f"ถอนการลงทะเบียนสำเร็จ {succeeded} รายการ"
        if skipped:
            message += f" · ข้ามรายการที่ถอนอยู่แล้ว {skipped} รายการ"
        if data["failed"]:
            message += f" · ไม่สำเร็จ {data['failed']} รายการ"
        return success_response(data, message)

    @action(detail=False, methods=["post"], url_path="batch-delete")
    def batch_delete(self, request):
        """Delete many enrollments — only rows without attendance history."""
        ids, error = self._batch_ids(request)
        if error:
            return error
        scoped = {obj.pk: obj for obj in self.get_queryset().filter(pk__in=ids)}
        results = []
        succeeded = skipped = 0
        for pk in ids:
            instance = scoped.get(pk)
            if instance is None:
                results.append(
                    {
                        "id": str(pk),
                        "student_code": "",
                        "course_code": "",
                        "ok": False,
                        "skipped": False,
                        "code": "NOT_FOUND",
                        "message": "ไม่พบรายการหรือไม่มีสิทธิ์จัดการ",
                    }
                )
                continue
            record_count = getattr(instance, "attendance_record_count", None)
            if record_count is None:
                record_count = self._record_count(instance)
            if record_count:
                results.append(
                    self._batch_result(
                        instance, ok=False, code="HAS_ATTENDANCE",
                        message=(
                            f"มีประวัติเช็คชื่อ {record_count} ครั้ง — "
                            "ใช้ถอนการลงทะเบียนแทนการลบ"
                        ),
                    )
                )
                continue
            resource_id = instance.pk
            metadata = self._enrollment_meta(instance)
            result = self._batch_result(instance, ok=True)
            with transaction.atomic():
                log_audit(
                    request.user, "enrollment_delete", "enrollment", resource_id,
                    metadata={**metadata, "batch": True, "batch_size": len(ids)},
                    request=request,
                )
                instance.delete()
            succeeded += 1
            results.append(result)
        data = self._batch_data(ids, results, succeeded, skipped)
        message = f"ลบการลงทะเบียนสำเร็จ {succeeded} รายการ"
        if data["failed"]:
            message += f" · ไม่สำเร็จ {data['failed']} รายการ"
        return success_response(data, message)

    @action(detail=True, methods=["post"], url_path="withdraw")
    def withdraw(self, request, pk=None):
        """Withdraw (ถอน) — keep the row and all attendance history."""
        instance = self.get_object()
        self._own_offering_or_403(instance.course_offering)
        if instance.enrollment_status == "dropped":
            return success_response(
                EnrollmentSerializer(instance).data, "รายการนี้ถูกถอนการลงทะเบียนอยู่แล้ว"
            )
        if instance.enrollment_status == "completed":
            return error_response(
                "รายวิชานี้จบรายวิชาแล้ว — ไม่สามารถถอนการลงทะเบียนได้",
                "INVALID_STATUS",
                status.HTTP_400_BAD_REQUEST,
            )
        reason = str(request.data.get("reason", "")).strip()[:500]
        instance.enrollment_status = "dropped"
        instance.save(update_fields=["enrollment_status", "updated_at"])
        log_audit(
            request.user, "enrollment_withdraw", "enrollment", instance.pk,
            metadata={**self._enrollment_meta(instance), "reason": reason},
            request=request,
        )
        return success_response(
            EnrollmentSerializer(instance).data,
            "ถอนการลงทะเบียนสำเร็จ — ประวัติการเช็คชื่อยังอยู่ครบ",
        )

    @action(detail=True, methods=["post"], url_path="reinstate")
    def reinstate(self, request, pk=None):
        """Undo a withdrawal — only while the offering is still running."""
        instance = self.get_object()
        self._own_offering_or_403(instance.course_offering)
        if instance.enrollment_status == "enrolled":
            return success_response(
                EnrollmentSerializer(instance).data, "รายการนี้ลงทะเบียนอยู่แล้ว"
            )
        if instance.enrollment_status == "completed":
            return error_response(
                "รายการนี้จบรายวิชาแล้ว — ไม่สามารถลงทะเบียนใหม่ได้",
                "INVALID_STATUS",
                status.HTTP_400_BAD_REQUEST,
            )
        if instance.course_offering.status in {"cancelled", "completed"}:
            return error_response(
                "รายวิชาที่เปิดสอนนี้ปิดรับลงทะเบียนแล้ว — ไม่สามารถลงทะเบียนใหม่ได้",
                "OFFERING_CLOSED",
                status.HTTP_400_BAD_REQUEST,
            )
        duplicate = Enrollment.objects.filter(
            student=instance.student,
            course_offering__course=instance.course_offering.course,
            course_offering__academic_term=instance.course_offering.academic_term,
            enrollment_status="enrolled",
        ).exclude(pk=instance.pk).exists()
        if duplicate:
            return error_response(
                "นักศึกษาลงทะเบียนรายวิชานี้ในภาคการศึกษาเดียวกันแล้ว",
                "DUPLICATE",
                status.HTTP_400_BAD_REQUEST,
            )
        reason = str(request.data.get("reason", "")).strip()[:500]
        instance.enrollment_status = "enrolled"
        instance.save(update_fields=["enrollment_status", "updated_at"])
        log_audit(
            request.user, "enrollment_reinstate", "enrollment", instance.pk,
            metadata={**self._enrollment_meta(instance), "reason": reason},
            request=request,
        )
        return success_response(
            EnrollmentSerializer(instance).data, "ลงทะเบียนใหม่สำเร็จ"
        )

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
        if offering.status in {"cancelled", "completed"}:
            return error_response(
                "ไม่สามารถลงทะเบียนรายวิชาที่ปิดรับลงทะเบียนแล้วได้",
                "OFFERING_CLOSED",
                400,
            )

        students = StudentProfile.objects.filter(class_group_id=group_id, status="active")
        created = skipped = dropped = 0
        with transaction.atomic():
            for student in students:
                enrollment, is_new = Enrollment.objects.get_or_create(
                    student=student, course_offering=offering,
                )
                if is_new:
                    created += 1
                elif enrollment.enrollment_status == "dropped":
                    dropped += 1
                else:
                    skipped += 1
        log_audit(
            request.user, "enrollment_bulk_create", "enrollment", offering.pk,
            metadata={
                "class_group": str(group_id), "created": created,
                "skipped": skipped, "dropped": dropped,
            },
            request=request,
        )
        return success_response(
            {
                "created": created, "skipped": skipped, "dropped": dropped,
                "course_offering": offering_id,
            },
            f"ลงทะเบียนเพิ่ม {created} คน (มีอยู่ก่อนแล้วข้าม {skipped} คน"
            + (f", ถอนอยู่ {dropped} คน" if dropped else "")
            + ")",
        )
