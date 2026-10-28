"use client";
/** Admin instructor accounts — custom create flow (user + profile in one). */
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { confirmDialog, toastSuccess } from "@/lib/swal";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { useEffect, useState } from "react";
import type { InstructorProfile } from "@/lib/types";
import { alertError } from "@/lib/swal";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const createFormFields = [
  { name: "username", label: "ชื่อผู้ใช้", required: true },
  { name: "email", label: "อีเมล", required: false },
  { name: "password", label: "รหัสผ่าน", type: "password", required: true },
  { name: "employee_code", label: "รหัสพนักงาน", required: true },
  { name: "first_name", label: "ชื่อ", required: true },
  { name: "last_name", label: "นามสกุล", required: true },
  { name: "department", label: "ภาควิชา/สาขา", required: false },
] as const;

export default function AdminInstructorsPage() {
  const user = useRequireRole(["admin"]);
  const [rows, setRows] = useState<InstructorProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<InstructorProfile | null>(null);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  const refresh = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (search.trim()) params.search = search.trim();
      const { data, envelope } = await samsRequest<InstructorProfile[]>({ url: "/instructors/", params });
      setRows(data ?? []);
      setPages(envelope.pagination?.pages ?? 1);
      setCount(envelope.pagination?.count ?? (data?.length ?? 0));
    } catch (error) {
      setRows([]);
      await alertError("โหลดรายชื่ออาจารย์ไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Yield once so the first setState isn't synchronous within the effect.
    let cancelled = false;
    void (async () => {
      await Promise.resolve();
      if (!cancelled) await refresh();
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, search]);

  const openCreate = () => {
    setEditing(null);
    setForm({ email: "", department: "" });
    setModalOpen(true);
    void toastSuccess("แบบฟอร์มพร้อมใช้งาน");
  };

  const openEdit = (row: InstructorProfile) => {
    setEditing(row);
    setForm({
      username: row.username,
      email: row.email,
      employee_code: row.employee_code,
      first_name: row.first_name,
      last_name: row.last_name,
      department: row.department,
      password: "",
    });
    setModalOpen(true);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      if (editing) {
        await samsRequest({
          url: `/instructors/${editing.id}/`,
          method: "PATCH",
          data: {
            employee_code: form.employee_code,
            first_name: form.first_name,
            last_name: form.last_name,
            department: form.department,
          },
        });
        await toastSuccess("แก้ไขข้อมูลอาจารย์สำเร็จ");
      } else {
        await samsRequest({
          url: "/instructors/",
          method: "POST",
          data: form,
        });
        await toastSuccess("เพิ่มอาจารย์สำเร็จ (สร้างบัญชีให้อัตโนมัติ)");
      }
      setModalOpen(false);
      await refresh();
    } catch (error) {
      await alertError(
        editing ? "แก้ไขไม่สำเร็จ" : "เพิ่มอาจารย์ไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async (row: InstructorProfile) => {
    const confirmed = await confirmDialog({
      title: "ยืนยันการลบข้อมูลอาจารย์",
      text: `${row.first_name} ${row.last_name} (${row.employee_code})`,
      confirmText: "ลบ",
    });
    if (!confirmed) return;
    try {
      await samsRequest({ url: `/instructors/${row.id}/`, method: "DELETE" });
      await toastSuccess("ลบข้อมูลอาจารย์สำเร็จ");
      await refresh();
    } catch (error) {
      await alertError("ลบไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    }
  };

  return (
    <AppShell title="จัดการอาจารย์ผู้สอน">
      {!user && null}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <form
            className="flex flex-1 min-w-[240px] gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              setPage(1);
              setSearch(searchInput);
            }}
          >
            <input
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="ค้นหาด้วยรหัสพนักงาน/ชื่อ-นามสกุล/username…"
              className={`${inputClass} max-w-xs`}
            />
            <button
              type="submit"
              className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
            >
              ค้นหา
            </button>
          </form>
          <button
            type="button"
            onClick={openCreate}
            className="ml-auto rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
          >
            ＋ เพิ่มอาจารย์ (พร้อมบัญชี)
          </button>
        </div>

        <DataTable<InstructorProfile>
          columns={[
            { key: "employee_code", label: "รหัสพนักงาน" },
            { key: "name", label: "ชื่อ-นามสกุล", render: (r) => `${r.first_name} ${r.last_name}` },
            { key: "username", label: "ชื่อผู้ใช้" },
            { key: "email", label: "อีเมล" },
            { key: "department", label: "ภาควิชา", render: (r) => r.department || "-" },
            { key: "status", label: "สถานะ", render: (r) => <StatusBadge status={r.status} /> },
          ]}
          rows={rows}
          loading={loading}
          emptyMessage="ยังไม่มีข้อมูลอาจารย์ในระบบ"
          renderActions={(row) => (
            <>
              <button
                type="button"
                onClick={() => openEdit(row)}
                className="rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
              >
                แก้ไข
              </button>
              <button
                type="button"
                onClick={() => void doDelete(row)}
                className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
              >
                ลบ
              </button>
            </>
          )}
        />
        <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => !saving && setModalOpen(false)} />
          <form
            onSubmit={(e) => void submit(e)}
            className="relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="mb-1 text-lg font-semibold text-slate-900">
              {editing ? "แก้ไขข้อมูลอาจารย์" : "เพิ่มอาจารย์ (สร้างบัญชีผู้ใช้อัตโนมัติ)"}
            </h2>
            {!editing && (
              <p className="mb-3 text-xs text-slate-500">
                ระบบจะสร้างบัญชีผู้ใช้ให้อาจารย์พร้อมโปรไฟล์ในคำขอเดียว รหัสผ่านต้องผ่านเกณฑ์ความปลอดภัย
              </p>
            )}
            <div className="space-y-3">
              {createFormFields.map((f) => (
                <div key={f.name} className="flex flex-col gap-1">
                  <label htmlFor={`instr-${f.name}`} className="text-sm font-medium text-slate-700">
                    {f.label}
                    {f.required && <span className="text-red-500"> *</span>}
                  </label>
                  {editing && f.name === "username" ? (
                    <div className="rounded-lg bg-slate-100 px-3 py-2 text-sm text-slate-600">{editing.username}</div>
                  ) : editing && (f.name === "password" || f.name === "email") ? (
                    f.name === "email" ? (
                      <input
                        id={`instr-${f.name}`}
                        type="email"
                        value={form[f.name] ?? ""}
                        disabled
                        className={`${inputClass} bg-slate-100 text-slate-500`}
                      />
                    ) : null
                  ) : (
                    <input
                      id={`instr-${f.name}`}
                      type={"type" in f ? f.type : "text"}
                      required={"required" in f ? f.required : false}
                      value={form[f.name] ?? ""}
                      onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                      className={inputClass}
                    />
                  )}
                </div>
              ))}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                disabled={saving}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                ยกเลิก
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
              >
                {saving ? "กำลังบันทึก…" : "บันทึก"}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
