"use client";
/** Admin student accounts — CRUD + CSV bulk import (real progress from API). */
import { useEffect, useMemo, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { loadOptions, type Option } from "@/lib/options";
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

type GroupOption = Option & { programId: string };

/** โหลดกลุ่มเรียนพร้อม program id เพื่อกรองตามหลักสูตรที่เลือก */
async function loadClassGroupOptions(): Promise<GroupOption[]> {
  const out: GroupOption[] = [];
  let page = 1;
  for (;;) {
    const { data, envelope } = await samsRequest<
      { results?: Record<string, unknown>[] } | Record<string, unknown>[]
    >({
      url: "/class-groups/",
      params: { page, page_size: 100 },
    });
    const rows = Array.isArray(data) ? data : data.results ?? [];
    for (const row of rows) {
      const code = String(row.group_code ?? "");
      const name = String(row.group_name ?? "");
      out.push({
        value: String(row.id),
        label: [code, name].filter(Boolean).join(" · ") || String(row.id),
        programId: String(row.program ?? ""),
      });
    }
    const pages = envelope.pagination?.pages ?? 1;
    if (pages > page && rows.length > 0) {
      page += 1;
    } else {
      break;
    }
  }
  return out;
}

export default function AdminStudentsPage() {
  const user = useRequireRole(["admin"]);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [importing, setImporting] = useState(false);
  const [refreshTick, setRefreshTick] = useState(0);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  // ── import scope modal (หลักสูตร + กลุ่มเรียน) ──
  const [importOpen, setImportOpen] = useState(false);
  const [programs, setPrograms] = useState<Option[]>([]);
  const [groups, setGroups] = useState<GroupOption[]>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsLoaded, setOptionsLoaded] = useState(false);
  const [selectedProgram, setSelectedProgram] = useState("");
  const [selectedGroup, setSelectedGroup] = useState("");

  const visibleGroups = useMemo(
    () => groups.filter((g) => !selectedProgram || g.programId === selectedProgram),
    [groups, selectedProgram],
  );
  const canImport =
    Boolean(csvFile) && Boolean(selectedProgram) && Boolean(selectedGroup) && !importing;

  useEffect(() => {
    if (!importOpen || optionsLoaded) return;
    let cancelled = false;
    setOptionsLoading(true);
    (async () => {
      try {
        const [programOptions, groupOptions] = await Promise.all([
          loadOptions("programs"),
          loadClassGroupOptions(),
        ]);
        if (cancelled) return;
        setPrograms(programOptions);
        setGroups(groupOptions);
        setOptionsLoaded(true);
      } catch (error) {
        if (!cancelled) {
          await alertError(
            "โหลดหลักสูตร/กลุ่มเรียนไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
      } finally {
        if (!cancelled) setOptionsLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [importOpen, optionsLoaded]);

  useEffect(() => {
    if (!importOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !importing) setImportOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [importOpen, importing]);

  const openImportModal = () => {
    if (!csvFile) return;
    setSelectedProgram("");
    setSelectedGroup("");
    setImportOpen(true);
  };

  const importCsv = async () => {
    if (!csvFile || !selectedProgram || !selectedGroup) return;
    setImporting(true);
    try {
      const form = new FormData();
      form.append("file", csvFile);
      form.append("program", selectedProgram);
      form.append("class_group", selectedGroup);
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
      if (fileInputRef.current) fileInputRef.current.value = "";
      setImportOpen(false);
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
              ref={fileInputRef}
              id="csv"
              type="file"
              accept=".csv,text/csv"
              disabled={importing}
              onChange={(e) => setCsvFile(e.target.files?.[0] ?? null)}
              className={inputClass}
            />
            <p className="text-xs text-slate-500">
              ต้องมีคอลัมน์: username, student_code, first_name, last_name, password (email, academic_year_level เป็นทางเลือก) — ขนาดไม่เกิน 2MB
            </p>
            <p className="text-xs text-slate-500">
              หลังเลือกไฟล์แล้วกด “นำเข้าไฟล์” ระบบจะให้เลือกหลักสูตรและกลุ่มเรียนก่อนยืนยัน
            </p>
          </div>
          <button
            type="button"
            disabled={!csvFile || importing}
            onClick={openImportModal}
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {importing ? "กำลังนำเข้า…" : "นำเข้าไฟล์"}
          </button>
        </div>
      </div>

      {importOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => !importing && setImportOpen(false)}
          />
          <form
            role="dialog"
            aria-modal="true"
            aria-labelledby="import-modal-title"
            onSubmit={(e) => {
              e.preventDefault();
              void importCsv();
            }}
            className="relative z-10 w-full max-w-lg rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 id="import-modal-title" className="mb-1 text-lg font-semibold text-slate-900">
              นำเข้านักศึกษาชุดจากไฟล์ CSV
            </h2>
            <p className="mb-4 truncate text-sm text-slate-500" title={csvFile?.name}>
              ไฟล์: <span className="font-medium text-slate-700">{csvFile?.name}</span>
            </p>

            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="import-program" className="text-sm font-medium text-slate-700">
                  หลักสูตร <span className="text-red-500">*</span>
                </label>
                <select
                  id="import-program"
                  required
                  value={selectedProgram}
                  disabled={optionsLoading || importing}
                  onChange={(e) => {
                    setSelectedProgram(e.target.value);
                    setSelectedGroup("");
                  }}
                  className={inputClass}
                >
                  <option value="">
                    {optionsLoading ? "กำลังโหลด…" : "— เลือกหลักสูตร —"}
                  </option>
                  {programs.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="import-class-group" className="text-sm font-medium text-slate-700">
                  กลุ่มเรียน <span className="text-red-500">*</span>
                </label>
                <select
                  id="import-class-group"
                  required
                  value={selectedGroup}
                  disabled={!selectedProgram || optionsLoading || importing}
                  onChange={(e) => setSelectedGroup(e.target.value)}
                  className={inputClass}
                >
                  <option value="">
                    {!selectedProgram
                      ? "— เลือกหลักสูตรก่อน —"
                      : optionsLoading
                        ? "กำลังโหลด…"
                        : "— เลือกกลุ่มเรียน —"}
                  </option>
                  {visibleGroups.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                {selectedProgram && !optionsLoading && visibleGroups.length === 0 && (
                  <p className="text-xs text-amber-600">
                    ยังไม่มีกลุ่มเรียนในหลักสูตรนี้ — กรุณาสร้างกลุ่มเรียนก่อนนำเข้า
                  </p>
                )}
              </div>

              <p className="rounded-lg bg-blue-50 px-3 py-2 text-xs text-blue-800">
                หลักสูตรและกลุ่มเรียนที่เลือกจะถูกกำหนดให้นักศึกษาทุกคนในไฟล์นี้
                (ชั้นปีเริ่มต้นใช้ตามกลุ่มเรียน หากไฟล์ไม่มีคอลัมน์ academic_year_level)
              </p>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                disabled={importing}
                onClick={() => setImportOpen(false)}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                ยกเลิก
              </button>
              <button
                type="submit"
                disabled={!canImport}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
              >
                {importing ? "กำลังนำเข้า…" : "ยืนยันนำเข้า"}
              </button>
            </div>
          </form>
        </div>
      )}

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
