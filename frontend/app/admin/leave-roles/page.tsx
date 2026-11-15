"use client";
/**
 * Admin: approval workflow role assignments (Phase 2).
 *
 * `LeaveRoleAssignment` is the single source of truth for who reviews a leave
 * request. A more specific scope wins when a request is submitted:
 * กลุ่มเรียน+ภาค > กลุ่มเรียน > หลักสูตร+ภาค > หลักสูตร > ทั้งระบบ.
 */
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import type { LeaveRoleAssignment } from "@/lib/types";

const ROLE_OPTIONS = [
  { value: "advisor", label: "อาจารย์ที่ปรึกษา" },
  { value: "program_head", label: "หัวหน้าหน่วยหลักสูตร" },
  { value: "final_approver", label: "ผู้มีอำนาจอนุมัติ" },
];

const fields: FieldDef[] = [
  {
    name: "role_type",
    label: "บทบาท Workflow",
    type: "select",
    required: true,
    options: ROLE_OPTIONS,
    defaultValue: "advisor",
  },
  {
    name: "user",
    label: "ผู้รับผิดชอบ (พิมพ์ชื่อหรือ username)",
    type: "select-search",
    required: true,
    optionsKey: "users",
    placeholder: "พิมพ์ชื่อ อาจารย์/ผู้ดูแลระบบ…",
    hint: "อาจารย์ที่ปรึกษาและหัวหน้าหน่วยหลักสูตรต้องเป็นบัญชีอาจารย์ ส่วนผู้อนุมัติเป็นอาจารย์หรือผู้ดูแลระบบได้",
  },
  {
    name: "program",
    label: "หลักสูตร (ขอบเขต)",
    type: "select",
    optionsKey: "programs",
    hint: "เว้นว่าง = ทั้งระบบ (เฉพาะผู้อนุมัติ)",
  },
  {
    name: "class_group",
    label: "กลุ่มเรียน (ถ้าเฉพาะกลุ่ม)",
    type: "select",
    optionsKey: "class-groups",
  },
  {
    name: "academic_term",
    label: "ภาคการศึกษา (ถ้าเฉพาะภาค)",
    type: "select",
    optionsKey: "academic-terms",
    hint: "เว้นว่าง = ทุกภาคเรียน",
  },
  {
    name: "is_active",
    label: "เปิดใช้งาน",
    type: "checkbox",
    hint: "ปิดเพื่อเลิกมอบหมายโดยไม่ลบประวัติ",
  },
];

function scopeLabel(row: LeaveRoleAssignment): string {
  const parts: string[] = [];
  parts.push(row.program_name ?? "ทั้งระบบ");
  if (row.class_group_name) parts.push(`กลุ่ม ${row.class_group_name}`);
  if (row.academic_term) parts.push(`ภาค ${row.term_label}`);
  return parts.join(" · ");
}

export default function AdminLeaveRolesPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="ผู้รับผิดชอบ Workflow ใบลา">
      {!user && null}
      <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-900">
        <p className="font-medium">ลำดับความเฉพาะเจาะจงของขอบเขต</p>
        <p className="mt-1 text-blue-800">
          กลุ่มเรียน + ภาคการศึกษา &gt; กลุ่มเรียน &gt; หลักสูตร + ภาคการศึกษา &gt;
          หลักสูตร &gt; ทั้งระบบ — ระบบจะบันทึกผู้รับผิดชอบลงในคำร้องตอนนักศึกษาส่ง
          และคำร้องที่อยู่ระหว่างพิจารณาจะไม่เปลี่ยนผู้รับผิดชอบย้อนหลัง
        </p>
        <p className="mt-1 text-blue-800">
          ต้องมีผู้รับผิดชอบครบทั้ง 3 บทบาท มิฉะนั้นนักศึกษาจะส่งใบลาไม่ได้
          (เมื่อเพิ่มผู้รับผิดชอบใหม่ ระบบจะเติมให้คำร้องที่ยังไม่มีผู้รับผิดชอบโดยอัตโนมัติ)
        </p>
      </div>
      <CrudPage<LeaveRoleAssignment>
        title="ผู้รับผิดชอบ Workflow"
        basePath="/leave-role-assignments/"
        fields={fields}
        createTitle="เพิ่มผู้รับผิดชอบ"
        searchPlaceholder="ค้นหาชื่อผู้รับผิดชอบ/หลักสูตร…"
        emptyMessage="ยังไม่มีการมอบหมายบทบาท Workflow"
        deleteLabel="ลบการมอบหมาย"
        columns={[
          {
            key: "role_type",
            label: "บทบาท",
            render: (row) => row.role_type_display,
          },
          {
            key: "user_name",
            label: "ผู้รับผิดชอบ",
            render: (row) => (
              <div>
                <div className="font-medium text-slate-800">{row.user_name}</div>
                <div className="text-xs text-slate-500">{row.user_username}</div>
              </div>
            ),
          },
          {
            key: "scope",
            label: "ขอบเขต",
            render: (row) => scopeLabel(row),
          },
          {
            key: "is_active",
            label: "สถานะ",
            render: (row) => (
              <StatusBadge status={row.is_active ? "active" : "inactive"} />
            ),
          },
        ]}
        filters={[
          { name: "role_type", label: "บทบาท", options: ROLE_OPTIONS },
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
