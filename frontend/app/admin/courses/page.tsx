"use client";
/** Admin course master-data management. */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { Course } from "@/lib/types";

const fields: FieldDef[] = [
  { name: "course_code", label: "รหัสรายวิชา", type: "text", required: true, placeholder: "เช่น IT211" },
  { name: "course_name", label: "ชื่อรายวิชา", type: "text", required: true },
  { name: "credits", label: "หน่วยกิต", type: "number", step: "0.5", min: 0, max: 9, defaultValue: "3" },
  { name: "description", label: "รายละเอียดรายวิชา", type: "textarea" },
  { name: "is_active", label: "เปิดใช้งาน", type: "checkbox", hint: "รายวิชานี้เปิดสอนได้" },
];

export default function AdminCoursesPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการรายวิชา">
      {!user && null}
      <CrudPage<Course>
        title="รายวิชา"
        basePath="/courses/"
        fields={fields}
        createTitle="เพิ่มรายวิชา"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อรายวิชา…"
        emptyMessage="ยังไม่มีรายวิชาในระบบ"
        columns={[
          { key: "course_code", label: "รหัสรายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "credits", label: "หน่วยกิต", render: (row) => String(row.credits) },
          { key: "is_active", label: "สถานะ", render: (row) => <StatusBadge status={row.is_active ? "active" : "inactive"} /> },
        ]}
        filters={[
          {
            name: "is_active",
            label: "สถานะ",
            options: [
              { value: "true", label: "เปิดใช้งาน" },
              { value: "false", label: "ปิดใช้งาน" },
            ],
          },
        ]}
      />
    </AppShell>
  );
}
