"use client";
/** Instructor attendance sessions — create sessions + jump to live control room. */
import Link from "next/link";
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { formatThaiDate, formatThaiTime, formatThaiDateTime } from "@/lib/format";
import type { AttendanceSession } from "@/lib/types";

const fields: FieldDef[] = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอนของฉัน", type: "select", required: true, optionsKey: "course-offerings" },
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

export default function InstructorAttendancePage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="เปิดเช็คชื่อ — คาบเรียนของฉัน">
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
        filters={[{ name: "status", label: "สถานะคาบ", options: SESSION_STATUS_OPTIONS }]}
        canDelete={false}
        rowActions={(row) => (
          <Link
            href={`/instructor/attendance/${row.id}`}
            className="rounded-lg bg-blue-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-800"
          >
            เข้าควบคุมคาบ
          </Link>
        )}
      />
    </AppShell>
  );
}
