"use client";
/**
 * Approval detail (Phase 2).
 *
 * Shows the full request, the sequential workflow and the actions the current
 * user may take. `available_actions` comes from the server and every endpoint
 * re-checks the current step/assignee, so hiding a button here is UX only.
 */
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
import { alertError, confirmDialog, toastSuccess } from "@/lib/swal";
import type { LeaveCourse, LeaveRequest, LeaveRequestStatus } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const OVERRIDE_TARGET_OPTIONS: {
  value: Exclude<LeaveRequestStatus, "draft" | "submitted">;
  label: string;
}[] = [
  { value: "pending_advisor_review", label: "ส่งกลับไปขั้นอาจารย์ที่ปรึกษา" },
  { value: "pending_program_head_review", label: "ส่งไปขั้นหัวหน้าหน่วยหลักสูตร" },
  { value: "pending_final_approval", label: "ส่งไปขั้นผู้มีอำนาจอนุมัติ" },
  { value: "approved", label: "อนุมัติ (approved)" },
  { value: "rejected", label: "ไม่อนุมัติ (rejected)" },
  { value: "returned", label: "ส่งกลับเพื่อแก้ไข (returned)" },
  { value: "cancelled", label: "ยกเลิกคำร้อง (cancelled)" },
];

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

export default function ApprovalDetailPage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>
      }
    >
      <ApprovalDetailContent />
    </Suspense>
  );
}

function ApprovalDetailContent() {
  const user = useRequireRole(["instructor", "admin"]);
  const params = useParams<{ id: string }>();
  const requestId = params.id;
  const [request, setRequest] = useState<LeaveRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [comment, setComment] = useState("");
  const [decision, setDecision] = useState<"approve" | "reject">("approve");
  const [overrideStatus, setOverrideStatus] = useState<string>("approved");
  const [overrideComment, setOverrideComment] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<LeaveRequest>({
          url: `/leave-approvals/${requestId}/`,
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

  const runAction = async (
    url: string,
    payload: Record<string, unknown>,
    successTitle: string,
  ) => {
    setBusy(true);
    try {
      const { data, envelope } = await samsRequest<LeaveRequest>({
        url,
        method: "POST",
        data: payload,
      });
      setRequest(data);
      setComment("");
      await toastSuccess(envelope.message || successTitle);
    } catch (error) {
      await alertError(
        "ดำเนินการไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  const submitOpinion = async () => {
    if (!request) return;
    if (!comment.trim()) {
      await alertError("กรุณาระบุความเห็น");
      return;
    }
    const action =
      request.current_step?.role_type === "advisor"
        ? "advisor-opinion"
        : "program-head-opinion";
    await runAction(
      `/leave-approvals/${request.id}/${action}/`,
      { comment: comment.trim() },
      "บันทึกความเห็นสำเร็จ",
    );
  };

  const submitFinalDecision = async () => {
    if (!request) return;
    if (decision === "reject" && !comment.trim()) {
      await alertError("กรุณาระบุเหตุผล", "การไม่อนุมัติต้องระบุเหตุผลประกอบ");
      return;
    }
    const confirmed = await confirmDialog({
      title: decision === "approve" ? "ยืนยันการอนุมัติ" : "ยืนยันการไม่อนุมัติ",
      text:
        decision === "approve"
          ? "คำร้องนี้จะถูกบันทึกว่าอนุมัติแล้ว"
          : "คำร้องนี้จะถูกบันทึกว่าไม่อนุมัติ",
      confirmText: decision === "approve" ? "อนุมัติ" : "ไม่อนุมัติ",
    });
    if (!confirmed) return;
    await runAction(
      `/leave-approvals/${request.id}/final-decision/`,
      { decision, comment: comment.trim() },
      "บันทึกผลการพิจารณาสำเร็จ",
    );
  };

  const submitReturn = async () => {
    if (!request) return;
    if (!comment.trim()) {
      await alertError("กรุณาระบุเหตุผล", "การส่งกลับเพื่อแก้ไขต้องระบุเหตุผล");
      return;
    }
    const confirmed = await confirmDialog({
      title: "ยืนยันการส่งกลับเพื่อแก้ไข",
      text: "นักศึกษาจะแก้ไขคำร้องและส่งใหม่ได้ โดยเริ่ม Workflow ที่ขั้นที่ 1 ใหม่",
      confirmText: "ส่งกลับ",
    });
    if (!confirmed) return;
    await runAction(
      `/leave-approvals/${request.id}/return/`,
      { comment: comment.trim() },
      "ส่งกลับเพื่อแก้ไขสำเร็จ",
    );
  };

  const submitOverride = async () => {
    if (!request) return;
    if (!overrideComment.trim()) {
      await alertError(
        "กรุณาระบุเหตุผล",
        "การดำเนินการแทนต้องระบุเหตุผลเพื่อบันทึกใน Audit Log",
      );
      return;
    }
    const confirmed = await confirmDialog({
      title: "ยืนยันการดำเนินการแทน",
      text: "ผู้ดูแลระบบจะเปลี่ยนสถานะคำร้องแทนผู้รับผิดชอบ และบันทึกเหตุผลลง Audit Log",
      confirmText: "ดำเนินการแทน",
    });
    if (!confirmed) return;
    await runAction(
      `/leave-requests/${request.id}/admin-override/`,
      { to_status: overrideStatus, comment: overrideComment.trim() },
      "ดำเนินการแทนสำเร็จ",
    );
  };

  if (loading || !request) {
    return (
      <AppShell title="พิจารณาคำร้องลา">
        <p className="animate-pulse text-slate-500">กำลังโหลดคำร้อง…</p>
      </AppShell>
    );
  }

  const canOpinion =
    hasWorkflowAction(request.available_actions, "advisor_opinion") ||
    hasWorkflowAction(request.available_actions, "program_head_opinion");
  const canFinal = hasWorkflowAction(request.available_actions, "final_decision");
  const canReturn = hasWorkflowAction(request.available_actions, "return");
  const canOverride = hasWorkflowAction(
    request.available_actions,
    "admin_override",
  );
  const hasActions = canOpinion || canFinal || canReturn || canOverride;

  return (
    <AppShell title="พิจารณาคำร้องลา">
      {!user && null}
      <div className="space-y-5">
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <Link href="/approvals" className="text-blue-700 hover:underline">
            ← กลับคิวพิจารณา
          </Link>
          <Link
            href={`/leaves/${request.id}/print`}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-auto rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
          >
            พิมพ์ใบลา
          </Link>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-slate-900">
              {request.student_code} — {request.student_name}
            </h2>
            <StatusBadge status={request.status} display={request.status_display} />
          </div>
          <div className="mt-0.5 text-xs text-slate-500">
            {request.student_program_name ?? "—"}
            {request.student_class_group_name
              ? ` · ${request.student_class_group_name}`
              : ""}
            {request.student_year_level
              ? ` · ชั้นปี ${request.student_year_level}`
              : ""}
          </div>
          <dl className="mt-4 grid gap-3 text-sm md:grid-cols-2">
            <div>
              <dt className="text-xs text-slate-500">ประเภทการลา</dt>
              <dd className="text-slate-800">{request.leave_type_display}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ช่วงที่ลา</dt>
              <dd className="text-slate-800">
                {formatThaiDate(request.start_date)} —{" "}
                {formatThaiDate(request.end_date)} ·{" "}
                {timeRange(request.start_time, request.end_time)} ·{" "}
                {request.total_days} วัน
              </dd>
            </div>
            <div className="md:col-span-2">
              <dt className="text-xs text-slate-500">เหตุผลการลา</dt>
              <dd className="whitespace-pre-wrap text-slate-800">
                {request.reason}
              </dd>
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
              <dt className="text-xs text-slate-500">ติดต่อระหว่างลา</dt>
              <dd className="text-slate-800">
                {request.contact_phone || "—"}
                {request.line_id ? ` · LINE ${request.line_id}` : ""}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">ส่งคำร้องเมื่อ</dt>
              <dd className="text-slate-800">
                {request.submitted_at
                  ? formatThaiDateTime(request.submitted_at)
                  : "-"}
              </dd>
            </div>
          </dl>
        </div>

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

        <LeaveWorkflowSection
          steps={request.workflow_steps}
          history={request.workflow_history}
          currentRoleType={request.current_step?.role_type ?? null}
        />

        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
          <h2 className="text-sm font-semibold text-slate-800">การพิจารณา</h2>
          {!hasActions && (
            <p className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
              ขั้นตอนนี้ไม่ใช่ของคุณ หรือคำร้องจบการพิจารณาแล้ว — คุณดูข้อมูลได้อย่างเดียว
            </p>
          )}

          {canOpinion && (
            <div className="mt-4 space-y-3">
              <p className="text-xs text-slate-500">
                {request.current_step?.role_type === "advisor"
                  ? "บันทึกความเห็นในฐานะอาจารย์ที่ปรึกษา แล้วส่งต่อให้หัวหน้าหน่วยหลักสูตร"
                  : "บันทึกความเห็นในฐานะหัวหน้าหน่วยหลักสูตร แล้วส่งต่อให้ผู้มีอำนาจอนุมัติ"}
              </p>
              <textarea
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder="ระบุความเห็น/ข้อเสนอแนะ"
                className={inputClass}
              />
              <div className="flex flex-wrap justify-end gap-2">
                {canReturn && (
                  <button
                    type="button"
                    onClick={() => void submitReturn()}
                    disabled={busy}
                    className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-700 hover:bg-orange-100 disabled:opacity-50"
                  >
                    ส่งกลับเพื่อแก้ไข
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => void submitOpinion()}
                  disabled={busy}
                  className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
                >
                  {busy ? "กำลังบันทึก…" : "บันทึกความเห็นและส่งต่อ"}
                </button>
              </div>
            </div>
          )}

          {canFinal && (
            <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
              <p className="text-xs text-slate-500">
                พิจารณาคำร้องพร้อมความเห็นจากอาจารย์ที่ปรึกษาและหัวหน้าหน่วยหลักสูตร
              </p>
              <div className="flex flex-wrap gap-4 text-sm text-slate-700">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="decision"
                    checked={decision === "approve"}
                    onChange={() => setDecision("approve")}
                    className="h-4 w-4"
                  />
                  อนุมัติ
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="decision"
                    checked={decision === "reject"}
                    onChange={() => setDecision("reject")}
                    className="h-4 w-4"
                  />
                  ไม่อนุมัติ
                </label>
              </div>
              <textarea
                rows={3}
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                placeholder={
                  decision === "reject"
                    ? "เหตุผลที่ไม่อนุมัติ *"
                    : "หมายเหตุ (ไม่บังคับ)"
                }
                className={inputClass}
              />
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => void submitFinalDecision()}
                  disabled={busy}
                  className={`rounded-lg px-4 py-2 text-sm font-medium text-white disabled:opacity-50 ${
                    decision === "approve"
                      ? "bg-emerald-600 hover:bg-emerald-700"
                      : "bg-red-600 hover:bg-red-700"
                  }`}
                >
                  {busy
                    ? "กำลังบันทึก…"
                    : decision === "approve"
                      ? "ยืนยันอนุมัติ"
                      : "ยืนยันไม่อนุมัติ"}
                </button>
              </div>
            </div>
          )}

          {canOverride && (
            <div className="mt-4 space-y-3 border-t border-slate-100 pt-4">
              <h3 className="text-sm font-semibold text-slate-800">
                สิทธิ์ผู้ดูแลระบบ — ดำเนินการแทน
              </h3>
              <p className="text-xs text-slate-500">
                ใช้เมื่อผู้รับผิดชอบไม่สามารถดำเนินการได้ตามกำหนด คำร้องที่จบแล้วจะแก้ไขไม่ได้
              </p>
              <div className="grid gap-3 md:grid-cols-[280px_1fr]">
                <div>
                  <label
                    htmlFor="override-status"
                    className="mb-1 block text-xs font-medium text-slate-500"
                  >
                    สถานะปลายทาง *
                  </label>
                  <select
                    id="override-status"
                    value={overrideStatus}
                    onChange={(e) => setOverrideStatus(e.target.value)}
                    className={inputClass}
                  >
                    {OVERRIDE_TARGET_OPTIONS.filter(
                      (option) => option.value !== request.status,
                    ).map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label
                    htmlFor="override-comment"
                    className="mb-1 block text-xs font-medium text-slate-500"
                  >
                    เหตุผลประกอบ *
                  </label>
                  <textarea
                    id="override-comment"
                    rows={3}
                    value={overrideComment}
                    onChange={(e) => setOverrideComment(e.target.value)}
                    placeholder="ระบุเหตุผลที่จะบันทึกใน Audit Log"
                    className={inputClass}
                  />
                </div>
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  onClick={() => void submitOverride()}
                  disabled={busy}
                  className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-700 hover:bg-red-100 disabled:opacity-50"
                >
                  ดำเนินการแทน
                </button>
              </div>
            </div>
          )}
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
            ความเห็นของอาจารย์รายวิชาแยกจาก Workflow อนุมัติหลัก และไม่เปลี่ยนสถานะการเข้าเรียนโดยอัตโนมัติ
          </p>
        </div>
      </div>
    </AppShell>
  );
}
