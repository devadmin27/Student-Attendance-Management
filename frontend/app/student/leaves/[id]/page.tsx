"use client";
/** Student leave detail — request info, per-course review status, actions. */
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError, confirmDialog, toastSuccess } from "@/lib/swal";
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

      {course.reviews.length === 0 ? (
        <p className="mt-3 text-xs text-slate-500">ยังไม่มีความคิดเห็นจากอาจารย์ผู้สอน</p>
      ) : (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          {course.reviews.map((review) => (
            <div key={review.id} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-medium text-slate-800">{review.reviewer_name}</span>
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

export default function StudentLeaveDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>
      }
    >
      <StudentLeaveDetailContent />
    </Suspense>
  );
}

function StudentLeaveDetailContent() {
  const user = useRequireRole(["student"]);
  const params = useParams<{ id: string }>();
  const requestId = params.id;
  const [request, setRequest] = useState<LeaveRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

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

  const submit = async () => {
    if (!request) return;
    setBusy(true);
    try {
      const { data, envelope } = await samsRequest<LeaveRequest>({
        url: `/leave-requests/${request.id}/submit/`,
        method: "POST",
        data: {},
      });
      setRequest(data);
      await toastSuccess(envelope.message);
    } catch (error) {
      await alertError(
        "ส่งคำร้องไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  const cancel = async () => {
    if (!request) return;
    const confirmed = await confirmDialog({
      title: "ยืนยันการยกเลิกคำร้อง",
      text: "คำร้องที่ยกเลิกแล้วจะไม่แสดงสถานะลาในหน้าคำนวณการเข้าเรียน",
      confirmText: "ยกเลิกคำร้อง",
    });
    if (!confirmed) return;
    setBusy(true);
    try {
      const { data, envelope } = await samsRequest<LeaveRequest>({
        url: `/leave-requests/${request.id}/cancel/`,
        method: "POST",
        data: {},
      });
      setRequest(data);
      await toastSuccess(envelope.message);
    } catch (error) {
      await alertError(
        "ยกเลิกคำร้องไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  if (loading || !request) {
    return (
      <AppShell title="รายละเอียดคำร้องลา">
        <p className="animate-pulse text-slate-500">กำลังโหลดคำร้อง…</p>
      </AppShell>
    );
  }

  return (
    <AppShell title="รายละเอียดคำร้องลา">
      {!user && null}
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <Link href="/student/leaves" className="text-blue-700 hover:underline">
            ← กลับรายการใบลา
          </Link>
          <span className="ml-auto flex flex-wrap gap-2">
            {request.is_editable && (
              <>
                <Link
                  href={`/student/leaves/${request.id}/edit`}
                  className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
                >
                  แก้ไข
                </Link>
                <button
                  type="button"
                  onClick={() => void submit()}
                  disabled={busy}
                  className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
                >
                  ส่งคำร้อง
                </button>
              </>
            )}
            {request.is_cancellable && (
              <button
                type="button"
                onClick={() => void cancel()}
                disabled={busy}
                className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
              >
                ยกเลิกคำร้อง
              </button>
            )}
          </span>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              ใบลา{request.leave_type_display}
            </h2>
            <StatusBadge status={request.status} display={request.status_display} />
          </div>
          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">ช่วงที่ลา</dt>
              <dd className="text-slate-800">
                {formatThaiDate(request.start_date)} — {formatThaiDate(request.end_date)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">เวลา</dt>
              <dd className="text-slate-800">
                {timeRange(request.start_time, request.end_time)}
              </dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-slate-500">เหตุผล</dt>
              <dd className="whitespace-pre-wrap text-slate-800">{request.reason}</dd>
            </div>
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
          <p className="mt-3 text-xs text-slate-500">
            ความเห็นของอาจารย์รายวิชาแยกจากสถานะคำร้องหลัก และไม่เปลี่ยนสถานะการเข้าเรียนโดยอัตโนมัติ
          </p>
        </div>
      </div>
    </AppShell>
  );
}
