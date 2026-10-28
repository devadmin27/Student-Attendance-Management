"use client";
/** Admin enrollment management. */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { formatThaiDateTime } from "@/lib/format";
import type { Enrollment } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "enrolled", label: "กำลังศึกษา" },
  { value: "dropped", label: "ถอนรายวิชา" },
  { value: "completed", label: "จบรายวิชา" },
];

const fields: FieldDef[] = [
  { name: "student", label: "นักศึกษา", type: "select", required: true, optionsKey: "students" },
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", type: "select", required: true, optionsKey: "course-offerings" },
  { name: "enrollment_status", label: "สถานะการลงทะเบียน", type: "select", options: STATUS_OPTIONS, defaultValue: "enrolled" },
];

export default function AdminEnrollmentsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการการลงทะเบียนเรียน">
      {!user && null}
      <CrudPage<Enrollment>
        title="การลงทะเบียน"
        basePath="/enrollments/"
        fields={fields}
        createTitle="เพิ่มการลงทะเบียน"
        searchPlaceholder="ค้นหาด้วยรหัสนักศึกษา/ชื่อ…"
        emptyMessage="ยังไม่มีรายการลงทะเบียน"
        columns={[
          { key: "student_code", label: "รหัสนักศึกษา" },
          { key: "student_name", label: "ชื่อ-นามสกุล" },
          { key: "course_code", label: "รายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "enrollment_status", label: "สถานะ", render: (row) => <StatusBadge status={row.enrollment_status} /> },
          { key: "enrolled_at", label: "ลงทะเบียนเมื่อ", render: (row) => formatThaiDateTime(row.enrolled_at) },
        ]}
        filters={[
          { name: "course_offering", label: "รายวิชาที่เปิดสอน", optionsKey: "course-offerings" },
          { name: "student", label: "นักศึกษา", optionsKey: "students" },
          { name: "enrollment_status", label: "สถานะ", options: STATUS_OPTIONS },
        ]}
      />
    </AppShell>
  );
}
