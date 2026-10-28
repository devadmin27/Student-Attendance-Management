"use client";
/** Admin program (หลักสูตร) management. */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { Program } from "@/lib/types";

const DEGREE_OPTIONS = [
  { value: "bachelor", label: "ปริญญาตรี" },
  { value: "master", label: "ปริญญาโท" },
  { value: "doctoral", label: "ปริญญาเอก" },
];

const fields: FieldDef[] = [
  { name: "program_code", label: "รหัสหลักสูตร", type: "text", required: true, placeholder: "เช่น IT-BSC" },
  { name: "program_name", label: "ชื่อหลักสูตร", type: "text", required: true },
  { name: "degree_level", label: "ระดับการศึกษา", type: "select", required: true, options: DEGREE_OPTIONS, defaultValue: "bachelor" },
  { name: "is_active", label: "เปิดใช้งาน", type: "checkbox", hint: "หลักสูตรนี้เปิดรับอยู่" },
];

export default function AdminProgramsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการหลักสูตร">
      {!user && null}
      <CrudPage<Program>
        title="หลักสูตร"
        basePath="/programs/"
        fields={fields}
        createTitle="เพิ่มหลักสูตร"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อหลักสูตร…"
        emptyMessage="ยังไม่มีหลักสูตรในระบบ"
        columns={[
          { key: "program_code", label: "รหัส" },
          { key: "program_name", label: "ชื่อหลักสูตร" },
          {
            key: "degree_level",
            label: "ระดับการศึกษา",
            render: (row) => DEGREE_OPTIONS.find((d) => d.value === row.degree_level)?.label ?? row.degree_level,
          },
          { key: "is_active", label: "สถานะ", render: (row) => <StatusBadge status={row.is_active ? "active" : "inactive"} /> },
        ]}
        filters={[
          { name: "degree_level", label: "ระดับการศึกษา", options: DEGREE_OPTIONS },
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
