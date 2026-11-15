"use client";
/** Admin read-only leave request detail. */
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import LeaveAttachmentList from "@/components/LeaveAttachments";
import LeaveWorkflowSection, {
  hasWorkflowAction,
} from "@/components/LeaveWorkflow";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { LeaveCourse, LeaveRequest } from "@/lib/types";

function timeRange(start: string | null, end: string | null): string {
  if (!start || !end) return "ลาทั้งวัน";
  return `${start.slice(0, 5)}–${end.slice(0, 5)}`;
}

function CourseCard({ course }: { course: LeaveCourse }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-slate-900">
            {course.course_code} — {course.course_name}
          </div>
          <div className="mt-0.5 text-xs text-slate-500">
            ภาค {course.term_label}
            {course.class_group_name ? ` · ${course.class_group_name}` : ""}
          </div>
          <div className="mt-1 text-xs text-slate-600">
            {course.schedules.length > 0
              ? course.schedules
                  .map(
                    (s) =>
                      `วัน${s.weekday_display} ${s.start_time}–${s.end_time}${
                        s.classroom ? ` (${s.classroom})` : ""
                      }`,
                  )
                  .join(" · ")
              : "ยังไม่มีตารางเรียน"}
          </div>
        </div>
        <StatusBadge
          status={course.review_status}
          display={course.review_status_display}
        />
      </div>
      <div className="mt-2 text-xs text-slate-500">
        ช่วงที่ได้รับผลกระทบ {formatThaiDate(course.affected_start_date)} —{" "}
        {formatThaiDate(course.affected_end_date)} ·{" "}
        {timeRange(course.affected_start_time, course.affected_end_time)}
      </div>
      {course.reviews.length > 0 && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          {course.reviews.map((review) => (
            <div key={review.id} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-medium text-slate-800">
                  {review.reviewer_name}
                </span>
                <StatusBadge
                  status={review.review_status}
                  display={review.review_status_display}
                />
                <span className="text-slate-400">
                  {formatThaiDateTime(review.created_at)}
                </span>
              </div>
              {review.comment && (
                <p className="mt-1 whitespace-pre-wrap text-xs text-slate-700">
                  {review.comment}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function AdminLeaveDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>
      }
    >
      <AdminLeaveDetailContent />
    </Suspense>
  );
}

function AdminLeaveDetailContent() {
  const user = useRequireRole(["admin"]);
  const params = useParams<{ id: string }>();
  const requestId = params.id;
  const [request, setRequest] = useState<LeaveRequest | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<LeaveRequest>({
          url: `/leave-requests/${requestId}/`,
        });
        if (!cancelled) setRequest(data);
      } catch (error) {
        if (!cancelled) {
          await alertError(
            "โหลดคำร้องไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  if (loading || !request) {
    return (
      <AppShell title="รายละเอียดคำร้องลา">
        <p className="animate-pulse text-slate-500">กำลังโหลดคำร้อง…</p>
      </AppShell>
    );
  }

  return (
    <AppShell title="รายละเอียดคำร้องลา (อ่านอย่างเดียว)">
      {!user && null}
      <div className="space-y-5">
        <div className="text-sm text-slate-600">
          <Link href="/admin/leaves" className="text-blue-700 hover:underline">
            ← กลับรายการคำร้องลา
          </Link>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              {request.student_code} — {request.student_name}
            </h2>
            <StatusBadge status={request.status} display={request.status_display} />
            <Link
              href={`/leaves/${request.id}/print`}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              พิมพ์ใบลา
            </Link>
            {hasWorkflowAction(request.available_actions, "admin_override") && (
              <Link
                href={`/approvals/${request.id}`}
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-100"
              >
                ดำเนินการแทน
              </Link>
            )}
          </div>
          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">ประเภทการลา</dt>
              <dd className="text-slate-800">{request.leave_type_display}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ช่วงที่ลา</dt>
              <dd className="text-slate-800">
                {formatThaiDate(request.start_date)} — {formatThaiDate(request.end_date)} ·{" "}
                {timeRange(request.start_time, request.end_time)}
              </dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-slate-500">เหตุผล</dt>
              <dd className="whitespace-pre-wrap text-slate-800">{request.reason}</dd>
            </div>
            {request.late_submission_reason && (
              <div className="md:col-span-2">
                <dt className="text-xs text-slate-500">เหตุผลการส่งย้อนหลัง</dt>
                <dd className="whitespace-pre-wrap text-slate-800">
                  {request.late_submission_reason}
                </dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-slate-500">สร้างเมื่อ</dt>
              <dd className="text-slate-800">{formatThaiDateTime(request.created_at)}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ส่งคำร้องเมื่อ</dt>
              <dd className="text-slate-800">
                {request.submitted_at ? formatThaiDateTime(request.submitted_at) : "-"}
              </dd>
            </div>
          </dl>
          <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            ผู้ดูแลระบบดูข้อมูลได้อย่างเดียว — หากจำเป็นต้องดำเนินการแทนผู้รับผิดชอบ
            ให้ใช้ปุ่ม “ดำเนินการแทน” ซึ่งต้องระบุเหตุผลและจะถูกบันทึกใน Audit Log
          </p>
        </div>

        <LeaveWorkflowSection
          steps={request.workflow_steps}
          history={request.workflow_history}
          currentRoleType={request.current_step?.role_type ?? null}
        />

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">
              เอกสารแนบ ({request.attachments.length})
            </h2>
            {request.requires_medical_certificate && (
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  request.medical_certificate_attached
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}
              >
                {request.medical_certificate_attached
                  ? "แนบใบรับรองแพทย์แล้ว"
                  : "ยังไม่ได้แนบใบรับรองแพทย์"}
              </span>
            )}
          </div>
          <LeaveAttachmentList
            attachments={request.attachments}
            emptyText="ไม่มีไฟล์แนบ"
          />
        </div>

        <div>
          <h2 className="mb-2 text-sm font-semibold text-slate-800">
            รายวิชาที่ได้รับผลกระทบ ({request.courses.length})
          </h2>
          <div className="space-y-3">
            {request.courses.map((course) => (
              <CourseCard key={course.id} course={course} />
            ))}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
