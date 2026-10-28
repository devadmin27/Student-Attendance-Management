"use client";
/** Admin class-group management. */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { useRequireRole } from "@/lib/auth-context";
import type { ClassGroup } from "@/lib/types";

const fields: FieldDef[] = [
  { name: "group_code", label: "รหัสกลุ่มเรียน", type: "text", required: true, placeholder: "เช่น IT-1" },
  { name: "group_name", label: "ชื่อกลุ่มเรียน", type: "text", required: true },
  { name: "program", label: "หลักสูตร", type: "select", required: true, optionsKey: "programs" },
  { name: "academic_year_level", label: "ชั้นปี", type: "number", min: 1, max: 8, defaultValue: 1 },
];

export default function AdminClassGroupsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการกลุ่มเรียน">
      {!user && null}
      <CrudPage<ClassGroup>
        title="กลุ่มเรียน"
        basePath="/class-groups/"
        fields={fields}
        createTitle="เพิ่มกลุ่มเรียน"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อกลุ่ม…"
        emptyMessage="ยังไม่มีกลุ่มเรียนในระบบ"
        columns={[
          { key: "group_code", label: "รหัสกลุ่ม" },
          { key: "group_name", label: "ชื่อกลุ่มเรียน" },
          { key: "program_name", label: "หลักสูตร" },
          { key: "academic_year_level", label: "ชั้นปี" },
        ]}
        filters={[{ name: "program", label: "หลักสูตร", optionsKey: "programs" }]}
      />
    </AppShell>
  );
}
