"use client";
/** Admin attendance-session management + lifecycle actions (open/pause/close/cancel). */
import Link from "next/link";
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { confirmDialog, toastSuccess, alertError } from "@/lib/swal";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime, formatThaiTime } from "@/lib/format";
import type { AttendanceSession } from "@/lib/types";

const fields: FieldDef[] = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", type: "select", required: true, optionsKey: "course-offerings" },
  { name: "session_date", label: "วันที่เรียน", type: "date", required: true },
  { name: "check_in_start", label: "เวลาเริ่มรับเช็คชื่อ", type: "datetime-local", required: true },
  { name: "check_in_end", label: "เวลาปิดรับเช็คชื่อ", type: "datetime-local", required: true },
  { name: "late_threshold_minutes", label: "เกณฑ์มาสาย (นาที) หลังเริ่มเช็คชื่อ", type: "number", min: 0, defaultValue: 15 },
];

const SESSION_STATUS_OPTIONS = [
  { value: "scheduled", label: "กำหนดการ" },
  { value: "open", label: "เปิดรับเช็คชื่อ" },
  { value: "paused", label: "หยุดชั่วคราว" },
  { value: "closed", label: "ปิดแล้ว" },
  { value: "cancelled", label: "ยกเลิก" },
];

async function lifecycleAction(session: AttendanceSession, action: string, refresh: () => Promise<void> | void) {
  const labels: Record<string, string> = {
    open: "เปิดเช็คชื่อและออก QR Code ให้คาบนี้",
    pause: "หยุดคาบนี้ชั่วคราว (QR ที่แสดงจะใช้ไม่ได้ทันที)",
    close: "ปิดคาบและบันทึกขาดเรียนผู้ที่ไม่ได้เช็คชื่อทั้งหมด",
    cancel: "ยกเลิกคาบเรียน (ไม่สามารถเช็คชื่อได้อีก)",
  };
  const confirmed = await confirmDialog({
    title: `ยืนยันการ${action === "close" ? "ปิดคาบ" : action === "open" ? "เปิดคาบ" : action === "pause" ? "หยุดคาบชั่วคราว" : "ยกเลิกคาบ"}`,
    text: labels[action] ?? "",
    confirmText: "ยืนยัน",
  });
  if (!confirmed) return;
  try {
    const { envelope } = await samsRequest({
      url: `/attendance/sessions/${session.id}/${action}/`,
      method: "POST",
      data: {},
    });
    await toastSuccess(envelope.message);
    await refresh();
  } catch (error) {
    await alertError(
      "จัดการคาบเรียนไม่สำเร็จ",
      error instanceof ApiError ? error.message : undefined,
    );
  }
}

export default function AdminSessionsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="คาบเรียนเช็คชื่อ (ทุกตาราง)">
      {!user && null}
      <CrudPage<AttendanceSession>
        title="คาบเรียน"
        basePath="/attendance/sessions/"
        fields={fields}
        createTitle="สร้างคาบเช็คชื่อ"
        searchPlaceholder="ค้นหาด้วยรหัสรายวิชา…"
        emptyMessage="ยังไม่มีคาบเรียน — สร้างคาบใหม่เพื่อเริ่มเช็คชื่อ"
        columns={[
          { key: "course_code", label: "รายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "term_label", label: "ภาคการศึกษา" },
          { key: "session_date", label: "วันเรียน", render: (row) => formatThaiDate(row.session_date) },
          {
            key: "window",
            label: "ช่วงเช็คชื่อ",
            render: (row) => `${formatThaiDateTime(row.check_in_start)} — ${formatThaiTime(row.check_in_end)}`,
          },
          {
            key: "counts",
            label: "เช็คชื่อแล้ว/ลงทะเบียน",
            className: "tabular-nums",
            render: (row) => `${row.checked_in_count}/${row.enrolled_count}`,
          },
          {
            key: "status",
            label: "สถานะ",
            render: (row) => <StatusBadge status={row.status} display={row.status_display} />,
          },
        ]}
        filters={[
          { name: "course_offering", label: "รายวิชา", optionsKey: "course-offerings" },
          { name: "status", label: "สถานะคาบ", options: SESSION_STATUS_OPTIONS },
        ]}
        rowActions={(row, refresh) =>
          row.status === "open" || row.status === "paused" || row.status === "scheduled" ? (
            <>
              {row.status !== "scheduled" && (
                <button
                  type="button"
                  onClick={() => void lifecycleAction(row, "close", refresh)}
                  className="rounded-lg border border-slate-300 bg-white px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                >
                  ปิดคาบ
                </button>
              )}
              {row.status === "open" && (
                <button
                  type="button"
                  onClick={() => void lifecycleAction(row, "pause", refresh)}
                  className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
                >
                  หยุดชั่วคราว
                </button>
              )}
              {(row.status === "paused" || row.status === "scheduled") && (
                <button
                  type="button"
                  onClick={() => void lifecycleAction(row, "open", refresh)}
                  className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
                >
                  เปิดเช็คชื่อ
                </button>
              )}
              <button
                type="button"
                onClick={() => void lifecycleAction(row, "cancel", refresh)}
                className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
              >
                ยกเลิกคาบ
              </button>
            </>
          ) : (
            <Link
              href={`/admin/attendance-records?session=${row.id}`}
              className="rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
            >
              ดูรายการ
            </Link>
          )
        }
      />
    </AppShell>
  );
}
