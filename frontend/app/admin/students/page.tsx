"use client";
/** Admin student accounts — CRUD + CSV bulk import (real progress from API). */
import { useState } from "react";
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError, toastSuccess } from "@/lib/swal";
import type { StudentProfile } from "@/lib/types";

const STATUS_OPTIONS = [
  { value: "active", label: "ใช้งานอยู่" },
  { value: "suspended", label: "ระงับการใช้งาน" },
  { value: "inactive", label: "ไม่ใช้งาน" },
];

const fields: FieldDef[] = [
  { name: "username", label: "ชื่อผู้ใช้", type: "text", required: true, createOnly: true },
  { name: "email", label: "อีเมล", type: "email", createOnly: true },
  { name: "password", label: "รหัสผ่าน", type: "password", required: true, createOnly: true },
  { name: "student_code", label: "รหัสนักศึกษา", type: "text", required: true },
  { name: "first_name", label: "ชื่อ", type: "text", required: true },
  { name: "last_name", label: "นามสกุล", type: "text", required: true },
  { name: "program", label: "หลักสูตร", type: "select", optionsKey: "programs" },
  {
    name: "academic_year_level",
    label: "ชั้นปี",
    type: "number",
    min: 1,
    max: 8,
    defaultValue: 1,
    hint: "1-8",
  },
  { name: "class_group", label: "กลุ่มเรียน", type: "select", optionsKey: "class-groups" },
  { name: "status", label: "สถานะนักศึกษา", type: "select", options: STATUS_OPTIONS, defaultValue: "active" },
];

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

export default function AdminStudentsPage() {
  const user = useRequireRole(["admin"]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);

  const importCsv = async () => {
    if (!csvFile) return;
    setImporting(true);
    try {
      const form = new FormData();
      form.append("file", csvFile);
      const { data, envelope } = await samsRequest<{ created: number; failed: { row: number; message: string }[] }>({
        url: "/students/import-csv/",
        method: "POST",
        data: form,
        headers: { "Content-Type": "multipart/form-data" },
      });
      await toastSuccess(envelope.message);
      if (data.failed.length > 0) {
        await alertError(
          `นำเข้าสำเร็จ ${data.created} รายการ แต่มี ${data.failed.length} บรรทัดไม่ผ่าน`,
          data.failed.map((e) => `แถว ${e.row}: ${e.message}`).join("\n"),
        );
      }
      setCsvFile(null);
      setRefreshTick((t) => t + 1);
    } catch (error) {
      await alertError(
        "นำเข้า CSV ไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setImporting(false);
    }
  };

  return (
    <AppShell title="จัดการนักศึกษา">
      {!user && null}
      <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="csv" className="text-sm font-medium text-slate-700">
              นำเข้านักศึกษาชุดจากไฟล์ CSV (UTF-8)
            </label>
            <input
              id="csv"
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
              className={inputClass}
            />
            <p className="text-xs text-slate-500">
              ต้องมีคอลัมน์: username, student_code, first_name, last_name, password (email, academic_year_level เป็นทางเลือก) — ขนาดไม่เกิน 2MB
            </p>
          </div>
          <button
            type="button"
            disabled={!csvFile || importing}
            onClick={() => void importCsv()}
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {importing ? "กำลังนำเข้า…" : "นำเข้าไฟล์"}
          </button>
        </div>
      </div>

      <CrudPage<StudentProfile>
        key={refreshTick}
        title="นักศึกษา"
        basePath="/students/"
        fields={fields}
        createTitle="เพิ่มนักศึกษา (พร้อมบัญชี)"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อ-นามสกุล/username…"
        emptyMessage="ยังไม่มีนักศึกษาในระบบ"
        columns={[
          { key: "student_code", label: "รหัสนักศึกษา" },
          {
            key: "student_name",
            label: "ชื่อ-นามสกุล",
            render: (row) => `${row.first_name} ${row.last_name}`,
          },
          { key: "program_name", label: "หลักสูตร", render: (row) => row.program_name ?? "-" },
          { key: "class_group_name", label: "กลุ่มเรียน", render: (row) => row.class_group_name ?? "-" },
          { key: "academic_year_level", label: "ชั้นปี" },
          { key: "status", label: "สถานะ", render: (row) => <StatusBadge status={row.status} /> },
        ]}
        filters={[
          { name: "program", label: "หลักสูตร", optionsKey: "programs" },
          { name: "class_group", label: "กลุ่มเรียน", optionsKey: "class-groups" },
          { name: "status", label: "สถานะ", options: STATUS_OPTIONS },
        ]}
        deleteLabel="ลบนักศึกษา"
      />
    </AppShell>
  );
}
