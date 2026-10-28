"use client";
/** Admin course-offering management (รายวิชาที่เปิดสอนในภาคการศึกษา). */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { CourseOffering } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "open", label: "เปิดรับลงทะเบียน" },
  { value: "in_progress", label: "กำลังเรียน" },
  { value: "completed", label: "จบภาคเรียนแล้ว" },
  { value: "cancelled", label: "ยกเลิก" },
];

const fields: FieldDef[] = [
  { name: "course", label: "รายวิชา", type: "select", required: true, optionsKey: "courses" },
  { name: "academic_term", label: "ภาคการศึกษา", type: "select", required: true, optionsKey: "academic-terms" },
  { name: "instructor", label: "อาจารย์ผู้รับผิดชอบ", type: "select", optionsKey: "instructors" },
  { name: "class_group", label: "กลุ่มเรียน (ถ้ามี)", type: "select", optionsKey: "class-groups" },
  { name: "status", label: "สถานะ", type: "select", options: STATUS_OPTIONS, defaultValue: "open" },
];

export default function AdminCourseOfferingsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการเปิดสอนรายวิชา">
      {!user && null}
      <CrudPage<CourseOffering>
        title="เปิดสอนรายวิชา"
        basePath="/course-offerings/"
        fields={fields}
        createTitle="เพิ่มการเปิดสอน"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อรายวิชา…"
        emptyMessage="ยังไม่มีการเปิดสอนรายวิชา"
        columns={[
          { key: "course_code", label: "รหัสรายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "term_label", label: "ภาคการศึกษา" },
          { key: "instructor_name", label: "อาจารย์", render: (row) => row.instructor_name ?? "-" },
          { key: "enrollment_count", label: "จำนวนลงทะเบียน", className: "tabular-nums" },
          { key: "status", label: "สถานะ", render: (row) => <StatusBadge status={row.status} /> },
        ]}
        filters={[
          { name: "academic_term", label: "ภาคการศึกษา", optionsKey: "academic-terms" },
          { name: "course", label: "รายวิชา", optionsKey: "courses" },
          { name: "status", label: "สถานะ", options: STATUS_OPTIONS },
        ]}
      />
    </AppShell>
  );
}
