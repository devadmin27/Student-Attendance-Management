"use client";
/**
 * Instructor leave-course review page.
 * Shows the full leave request for one course offering and lets any
 * instructor of that offering record a course-specific comment.
 * Never changes the leave request's own status.
 */
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError, toastSuccess } from "@/lib/swal";
import type {
  LeaveCourseInboxItem,
  LeaveCourseReviewStatus,
} from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const REVIEW_OPTIONS: {
  value: Exclude<LeaveCourseReviewStatus, "pending">;
  label: string;
}[] = [
  { value: "reviewed", label: "ให้ความเห็นแล้ว" },
  { value: "acknowledged", label: "รับทราบ" },
  { value: "rejected", label: "ไม่เห็นด้วย" },
];

function timeRange(start: string | null, end: string | null): string {
  if (!start || !end) return "ลาทั้งวัน";
  return `${start.slice(0, 5)}–${end.slice(0, 5)}`;
}

export default function InstructorLeaveDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>
      }
    >
      <InstructorLeaveDetailContent />
    </Suspense>
  );
}

function InstructorLeaveDetailContent() {
  const user = useRequireRole(["instructor"]);
  const params = useParams<{ id: string }>();
  const leaveCourseId = params.id;

  const [item, setItem] = useState<LeaveCourseInboxItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewStatus, setReviewStatus] = useState<
    Exclude<LeaveCourseReviewStatus, "pending">
  >("reviewed");
  const [comment, setComment] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<LeaveCourseInboxItem>({
          url: `/leave-courses/${leaveCourseId}/`,
        });
        if (!cancelled) setItem(data);
      } catch (error) {
        if (!cancelled) {
          await alertError(
            "โหลดคำร้องลาไม่สำเร็จ",
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
  }, [leaveCourseId]);

  const submitReview = async () => {
    if (!item) return;
    if (reviewStatus === "rejected" && !comment.trim()) {
      await alertError("กรุณาระบุเหตุผล", "การไม่เห็นด้วยต้องระบุเหตุผลประกอบ");
      return;
    }
    setSaving(true);
    try {
      const { data, envelope } = await samsRequest<LeaveCourseInboxItem>({
        url: `/leave-courses/${item.id}/review/`,
        method: "POST",
        data: { review_status: reviewStatus, comment: comment.trim() },
      });
      setItem(data);
      setComment("");
      await toastSuccess(envelope.message);
    } catch (error) {
      await alertError(
        "บันทึกผลการพิจารณาไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading || !item) {
    return (
      <AppShell title="พิจารณาคำร้องลารายวิชา">
        <p className="animate-pulse text-slate-500">กำลังโหลดคำร้องลา…</p>
      </AppShell>
    );
  }

  return (
    <AppShell title="พิจารณาคำร้องลารายวิชา">
      {!user && null}
      <div className="space-y-5">
        <div className="text-sm text-slate-600">
          <Link href="/instructor/leaves" className="text-blue-700 hover:underline">
            ← กลับรายการคำร้องลาในรายวิชา
          </Link>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              {item.student_code} — {item.student_name}
            </h2>
            <StatusBadge
              status={item.request_status}
              display={item.request_status_display}
            />
            <Link
              href={`/leaves/${item.leave_request_id}/print`}
              target="_blank"
              rel="noopener noreferrer"
              className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
            >
              พิมพ์ใบลา
            </Link>
          </div>
          <div className="mt-1 text-sm text-slate-600">
            {item.course_code} — {item.course_name} · ภาค {item.term_label}
            {item.class_group_name ? ` · ${item.class_group_name}` : ""}
          </div>

          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">ประเภทการลา</dt>
              <dd className="text-slate-800">{item.leave_type_display}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ช่วงที่ลา</dt>
              <dd className="text-slate-800">
                {formatThaiDate(item.start_date)} — {formatThaiDate(item.end_date)} ·{" "}
                {timeRange(item.start_time, item.end_time)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ช่วงที่กระทบรายวิชานี้</dt>
              <dd className="text-slate-800">
                {formatThaiDate(item.affected_start_date)} —{" "}
                {formatThaiDate(item.affected_end_date)} ·{" "}
                {timeRange(item.affected_start_time, item.affected_end_time)}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ส่งคำร้องเมื่อ</dt>
              <dd className="text-slate-800">
                {item.submitted_at ? formatThaiDateTime(item.submitted_at) : "-"}
              </dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-slate-500">เหตุผลการลา</dt>
              <dd className="whitespace-pre-wrap text-slate-800">{item.reason}</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold text-slate-800">
              ความเห็นอาจารย์รายวิชา
            </h2>
            <StatusBadge
              status={item.review_status}
              display={item.review_status_display}
            />
          </div>
          <p className="mt-1 text-xs text-slate-500">
            ความเห็นนี้แยกจากสถานะคำร้องหลัก และไม่เปลี่ยนสถานะการเข้าเรียนโดยอัตโนมัติ
          </p>

          {item.is_reviewable ? (
            <div className="mt-4 space-y-3">
              <div className="grid gap-3 md:grid-cols-[220px_1fr]">
                <div>
                  <label
                    htmlFor="review-status"
                    className="mb-1 block text-xs font-medium text-slate-500"
                  >
                    ผลการพิจารณา *
                  </label>
                  <select
                    id="review-status"
                    value={reviewStatus}
                    onChange={(e) =>
                      setReviewStatus(
                        e.target.value as Exclude<
                          LeaveCourseReviewStatus,
                          "pending"
                        >,
                      )
                    }
                    className={inputClass}
                  >
                    {REVIEW_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="review-comment"
                    className="mb-1 block text-xs font-medium text-slate-500"
                  >
                    ความคิดเห็น{" "}
                    {reviewStatus === "rejected" ? "*" : "(ไม่บังคับ)"}
                  </label>
                  <textarea
                    id="review-comment"
                    rows={3}
                    value={comment}
                    onChange={(e) => setComment(e.target.value)}
                    placeholder="ระบุความเห็นต่อการลาของนักศึกษาในรายวิชานี้"
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => void submitReview()}
                  disabled={saving}
                  className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
                >
                  {saving ? "กำลังบันทึก…" : "บันทึกผลการพิจารณา"}
                </button>
              </div>
            </div>
          ) : (
            <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              คำร้องนี้ไม่อยู่ในสถานะที่พิจารณาได้ (ต้องเป็นคำร้องที่ส่งแล้วและยังไม่ถูกยกเลิก)
            </p>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <h2 className="text-sm font-semibold text-slate-800">
            ประวัติการพิจารณา ({item.reviews.length})
          </h2>
          {item.reviews.length === 0 ? (
            <p className="mt-3 text-sm text-slate-500">ยังไม่มีความคิดเห็น</p>
          ) : (
            <div className="mt-3 space-y-2">
              {item.reviews.map((review) => (
                <div
                  key={review.id}
                  className="rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"
                >
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
      </div>
    </AppShell>
  );
}
