"use client";
/** Admin academic-term management. */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { AcademicTerm } from "@/lib/types";

const SEMESTER_OPTIONS = [
  { value: "1", label: "ภาคเรียนที่ 1" },
  { value: "2", label: "ภาคเรียนที่ 2" },
  { value: "3", label: "ภาคเรียนฤดูร้อน" },
];

const fields: FieldDef[] = [
  { name: "academic_year", label: "ปีการศึกษา (พ.ศ.)", type: "number", required: true, min: 2500, max: 2799, placeholder: "เช่น 2569" },
  { name: "semester", label: "ภาคการศึกษา", type: "select", required: true, options: SEMESTER_OPTIONS },
  { name: "start_date", label: "วันเริ่มต้นภาคเรียน", type: "date", required: true },
  { name: "end_date", label: "วันสิ้นสุดภาคเรียน", type: "date", required: true },
  { name: "is_active", label: "เปิดใช้งาน", type: "checkbox", hint: "ภาคเรียนนี้พร้อมใช้งาน" },
  { name: "is_current", label: "ภาคปัจจุบัน", type: "checkbox", hint: "กำหนดเป็นภาคปัจจุบัน (ได้ 1 ภาคเท่านั้น)" },
];

export default function AdminAcademicTermsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการภาคการศึกษา">
      {!user && null}
      <CrudPage<AcademicTerm>
        title="ภาคการศึกษา"
        basePath="/academic-terms/"
        fields={fields}
        createTitle="เพิ่มภาคการศึกษา"
        searchPlaceholder="ค้นหาปีการศึกษา/ภาค…"
        emptyMessage="ยังไม่มีข้อมูลภาคการศึกษา"
        columns={[
          { key: "academic_year", label: "ปีการศึกษา" },
          { key: "semester", label: "ภาคเรียน", render: (row) => row.semester_display },
          {
            key: "dates",
            label: "ช่วงเรียน",
            render: (row) => `${row.start_date} → ${row.end_date}`,
          },
          { key: "is_active", label: "เปิดใช้งาน", render: (row) => <StatusBadge status={row.is_active ? "active" : "inactive"} /> },
          {
            key: "is_current",
            label: "ภาคปัจจุบัน",
            render: (row) => (row.is_current ? <StatusBadge status="enrolled" display="ปัจจุบัน" /> : "-"),
          },
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
