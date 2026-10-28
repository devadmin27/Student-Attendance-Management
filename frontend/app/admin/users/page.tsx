"use client";
/** Admin user management (list/activate/suspend/delete + create). */
import { useCallback, useState } from "react";
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { formatThaiDate } from "@/lib/format";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError, toastSuccess } from "@/lib/swal";
import type { User } from "@/lib/types";

const ROLE_OPTIONS = [
  { value: "admin", label: "ผู้ดูแลระบบ" },
  { value: "instructor", label: "อาจารย์ผู้สอน" },
  { value: "student", label: "นักศึกษา" },
];

const fields: FieldDef[] = [
  { name: "username", label: "ชื่อผู้ใช้", type: "text", required: true, placeholder: "เช่น s650001" },
  { name: "email", label: "อีเมล", type: "email", placeholder: "name@university.ac.th" },
  {
    name: "role",
    label: "บทบาทในระบบ",
    type: "select",
    required: true,
    options: ROLE_OPTIONS,
    hint: "เปลี่ยนบทบาทได้เฉพาะผู้ดูแลระบบ",
  },
  {
    name: "password",
    label: "รหัสผ่าน",
    type: "password",
    required: true,
    createOnly: true,
    placeholder: "ขั้นต่ำ 8 ตัว ไม่เป็นรหัสธรรมดา",
  },
  {
    name: "confirm_password",
    label: "ยืนยันรหัสผ่าน",
    type: "password",
    required: true,
    createOnly: true,
  },
  { name: "is_active", label: "สถานะบัญชี", type: "checkbox", hint: "เปิดใช้งานบัญชี" },
];

export default function AdminUsersPage() {
  const user = useRequireRole(["admin"]);
  const [busyUserId, setBusyUserId] = useState<string | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  const setAccountState = useCallback(
    async (row: User, isActive: boolean) => {
      setBusyUserId(row.id);
      try {
        await samsRequest({
          url: `/users/${row.id}/${isActive ? "activate" : "suspend"}/`,
          method: "PATCH",
          data: {},
        });
        await toastSuccess(isActive ? "เปิดใช้งานบัญชีสำเร็จ" : "ระงับบัญชีสำเร็จ");
        setRefreshTick((t) => t + 1);
      } catch (error) {
        await alertError(
          "จัดการบัญชีไม่สำเร็จ",
          error instanceof ApiError ? error.message : undefined,
        );
      } finally {
        setBusyUserId(null);
      }
    },
    [],
  );

  return (
    <AppShell title="จัดการผู้ใช้งานระบบ">
      {!user && null}
      <CrudPage<User>
        key={refreshTick}
        title="ผู้ใช้งาน"
        basePath="/users/"
        fields={fields}
        createTitle="เพิ่มบัญชีผู้ใช้"
        searchPlaceholder="ค้นหาด้วย username หรืออีเมล…"
        emptyMessage="ยังไม่มีบัญชีผู้ใช้ในระบบ"
        columns={[
          { key: "username", label: "ชื่อผู้ใช้" },
          { key: "email", label: "อีเมล" },
          {
            key: "role",
            label: "บทบาท",
            render: (row) => ROLE_OPTIONS.find((r) => r.value === row.role)?.label ?? row.role,
          },
          {
            key: "student_code",
            label: "รหัสนักศึกษา",
            render: (row) => row.student_code ?? "-",
          },
          {
            key: "is_active",
            label: "สถานะ",
            render: (row) => <StatusBadge status={row.is_active ? "active" : "suspended"} />,
          },
          {
            key: "date_joined",
            label: "วันที่สมัคร",
            render: (row) => formatThaiDate(row.date_joined),
          },
        ]}
        filters={[
          { name: "role", label: "บทบาท", options: ROLE_OPTIONS },
          {
            name: "is_active",
            label: "สถานะบัญชี",
            options: [
              { value: "true", label: "ใช้งานอยู่" },
              { value: "false", label: "ถูกระงับ" },
            ],
          },
        ]}
        rowActions={(row, refresh) => (
          <>
            {row.is_active ? (
              <button
                type="button"
                disabled={busyUserId === row.id}
                onClick={() => void setAccountState(row, false).then(refresh)}
                className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
              >
                ระงับ
              </button>
            ) : (
              <button
                type="button"
                disabled={busyUserId === row.id}
                onClick={() => void setAccountState(row, true).then(refresh)}
                className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
              >
                เปิดใช้งาน
              </button>
            )}
          </>
        )}
        updateValue={(values) => ({
          ...values,
          // Never send password fields on PATCH (they are create-only).
          password: undefined,
          confirm_password: undefined,
        })}
      />
    </AppShell>
  );
}
