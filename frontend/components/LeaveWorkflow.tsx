"use client";
/**
 * Approval workflow timeline (Phase 2).
 *
 * Read-only presentation of LeaveWorkflowStep / LeaveWorkflowHistory data.
 * The server is the single source of truth: `available_actions` decides which
 * buttons a page may render, and every action is re-checked in the service
 * layer, so this component never grants access on its own.
 */
import { formatThaiDateTime } from "@/lib/format";
import { StatusBadge } from "@/components/ui";
import type {
  LeaveWorkflowAction,
  LeaveWorkflowHistoryEntry,
  LeaveWorkflowStep,
} from "@/lib/types";

const STEP_TONES: Record<string, string> = {
  pending: "border-amber-200 bg-amber-50",
  completed: "border-emerald-200 bg-emerald-50",
  skipped: "border-slate-200 bg-slate-50",
};

const STEP_MARKERS: Record<string, string> = {
  pending: "⏳",
  completed: "✅",
  skipped: "⤼",
};

export function hasWorkflowAction(
  actions: LeaveWorkflowAction[] | undefined,
  action: LeaveWorkflowAction,
): boolean {
  return Boolean(actions?.includes(action));
}

export function LeaveWorkflowSteps({
  steps,
  currentRoleType,
}: {
  steps: LeaveWorkflowStep[];
  /** Highlight the step that is waiting for an action right now. */
  currentRoleType?: string | null;
}) {
  if (steps.length === 0) {
    return (
      <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
        ยังไม่มีขั้นตอนการพิจารณา — ระบบจะสร้างขั้นตอนทั้ง 3 เมื่อนักศึกษาส่งคำร้อง
      </p>
    );
  }

  return (
    <ol className="space-y-2">
      {steps.map((step) => {
        const isCurrent = Boolean(
          currentRoleType &&
            step.role_type === currentRoleType &&
            step.status === "pending",
        );
        return (
          <li
            key={step.id}
            className={`rounded-xl border p-3 ${
              STEP_TONES[step.status] ?? "border-slate-200 bg-white"
            } ${isCurrent ? "ring-2 ring-blue-200" : ""}`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span aria-hidden>{STEP_MARKERS[step.status] ?? "•"}</span>
              <span className="text-sm font-semibold text-slate-900">
                ขั้นที่ {step.step_order} · {step.role_type_display}
              </span>
              <StatusBadge status={step.status} display={step.status_display} />
              {isCurrent && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[11px] font-medium text-blue-800">
                  กำลังรอดำเนินการ
                </span>
              )}
            </div>
            <dl className="mt-2 grid gap-1 text-xs text-slate-600 md:grid-cols-2">
              <div>
                <dt className="text-slate-400">ผู้รับผิดชอบ</dt>
                <dd>
                  {step.assignee_name ?? step.assignee_username ?? "ยังไม่กำหนด"}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">ดำเนินการเมื่อ</dt>
                <dd>
                  {step.acted_at
                    ? `${formatThaiDateTime(step.acted_at)} · ${
                        step.acted_by_name ?? "—"
                      }`
                    : "—"}
                </dd>
              </div>
            </dl>
            {step.comment && (
              <p className="mt-2 whitespace-pre-wrap rounded-lg bg-white/70 px-3 py-2 text-xs text-slate-700">
                {step.comment}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function LeaveWorkflowHistoryList({
  history,
}: {
  history: LeaveWorkflowHistoryEntry[];
}) {
  if (history.length === 0) {
    return <p className="text-xs text-slate-500">ยังไม่มีประวัติการดำเนินการ</p>;
  }
  return (
    <ol className="space-y-2 border-l border-slate-200 pl-4">
      {history.map((entry) => (
        <li key={entry.id} className="relative">
          <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-blue-400" />
          <div className="text-sm font-medium text-slate-800">
            {entry.action_display}
            {entry.role_type_display ? (
              <span className="ml-1 text-xs font-normal text-slate-500">
                ({entry.role_type_display})
              </span>
            ) : null}
          </div>
          <div className="text-xs text-slate-500">
            {entry.actor_name ? `${entry.actor_name} · ` : ""}
            {formatThaiDateTime(entry.created_at)}
          </div>
          {entry.comment && (
            <p className="mt-1 whitespace-pre-wrap text-xs text-slate-700">
              {entry.comment}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}

export default function LeaveWorkflowSection({
  steps,
  history,
  currentRoleType,
}: {
  steps: LeaveWorkflowStep[];
  history: LeaveWorkflowHistoryEntry[];
  currentRoleType?: string | null;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <h2 className="text-sm font-semibold text-slate-800">
        ขั้นตอนการพิจารณา (Workflow)
      </h2>
      <div className="mt-3">
        <LeaveWorkflowSteps steps={steps} currentRoleType={currentRoleType} />
      </div>
      <h3 className="mt-5 text-sm font-semibold text-slate-800">
        ประวัติการดำเนินการ
      </h3>
      <div className="mt-3">
        <LeaveWorkflowHistoryList history={history} />
      </div>
      <p className="mt-3 text-xs text-slate-400">
        ประวัติ Workflow นี้แสดงให้นักศึกษาและผู้พิจารณาเห็น — ส่วน Audit Log
        ความปลอดภัยดูได้เฉพาะผู้ดูแลระบบ
      </p>
    </div>
  );
}
