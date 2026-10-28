"use client";
/** Admin class-schedule management (ตารางเรียนประจำสัปดาห์ แยกจากคาบจริง). */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { ClassSchedule } from "@/lib/types";

const WEEKDAY_OPTIONS = [
  { value: "0", label: "จันทร์" },
  { value: "1", label: "อังคาร" },
  { value: "2", label: "พุธ" },
  { value: "3", label: "พฤหัสบดี" },
  { value: "4", label: "ศุกร์" },
  { value: "5", label: "เสาร์" },
  { value: "6", label: "อาทิตย์" },
];

const STATUS_OPTIONS = [
  { value: "planned", label: "กำหนดการ" },
  { value: "active", label: "ใช้งานอยู่" },
  { value: "cancelled", label: "ยกเลิก" },
];

const fields: FieldDef[] = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", type: "select", required: true, optionsKey: "course-offerings" },
  { name: "weekday", label: "วันเรียน", type: "select", required: true, options: WEEKDAY_OPTIONS, defaultValue: "0" },
  { name: "start_time", label: "เวลาเริ่มสอน", type: "time", required: true },
  { name: "end_time", label: "เวลาสิ้นสุด", type: "time", required: true },
  { name: "classroom", label: "ห้องเรียน", type: "text", placeholder: "เช่น SC-201" },
  { name: "status", label: "สถานะ", type: "select", options: STATUS_OPTIONS, defaultValue: "active" },
];

export default function AdminSchedulesPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการตารางเรียน">
      {!user && null}
      <CrudPage<ClassSchedule>
        title="ตารางเรียน"
        basePath="/class-schedules/"
        fields={fields}
        createTitle="เพิ่มสล็อตตารางเรียน"
        searchPlaceholder="ค้นหารายวิชา/ห้องเรียน…"
        emptyMessage="ยังไม่มีตารางเรียนในระบบ"
        columns={[
          { key: "course_code", label: "รายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "term_label", label: "ภาคการศึกษา" },
          {
            key: "weekday_display",
            label: "วันเรียน",
            render: (row) => `${row.weekday_display} ${row.start_time.slice(0, 5)}-${row.end_time.slice(0, 5)}`,
          },
          { key: "classroom", label: "ห้อง", render: (row) => row.classroom || "-" },
          { key: "status", label: "สถานะ", render: (row) => <StatusBadge status={row.status} /> },
        ]}
        filters={[
          { name: "course_offering", label: "รายวิชาที่เปิดสอน", optionsKey: "course-offerings" },
          { name: "weekday", label: "วันเรียน", options: WEEKDAY_OPTIONS },
          { name: "status", label: "สถานะ", options: STATUS_OPTIONS },
        ]}
      />
    </AppShell>
  );
}
