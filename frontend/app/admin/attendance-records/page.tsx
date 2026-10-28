"use client";
/** Attendance record inspection + status edit with mandatory reason (audited). */
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError, confirmDialog, toastSuccess, promptReason } from "@/lib/swal";
import type { AttendanceRecord } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const STATUS_OPTIONS = [
  { value: "", label: "ทุกสถานะ" },
  { value: "present", label: "เข้าเรียน" },
  { value: "late", label: "มาสาย" },
  { value: "absent", label: "ขาดเรียน" },
  { value: "excused", label: "ลา/ได้รับอนุญาต" },
];

export default function AdminAttendanceRecordsPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>}>
      <RecordsContent />
    </Suspense>
  );
}

function RecordsContent() {
  const user = useRequireRole(["admin"]);
  const searchParams = useSearchParams();
  const sessionFilter = searchParams.get("session") ?? "";
  const offeringFilter = searchParams.get("offering") ?? "";

  const [rows, setRows] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [status, setStatus] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  const refresh = async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (sessionFilter) params.attendance_session = sessionFilter;
      if (offeringFilter) params.attendance_session__course_offering = offeringFilter;
      if (status) params.status = status;
      if (search.trim()) params.search = search.trim();
      const { data, envelope } = await samsRequest<AttendanceRecord[]>({ url: "/attendance/records/", params });
      setRows(data ?? []);
      setPages(envelope.pagination?.pages ?? 1);
      setCount(envelope.pagination?.count ?? (data?.length ?? 0));
    } catch (error) {
      setRows([]);
      await alertError("โหลดรายการเช็คชื่อไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
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
  }, [page, status, search, sessionFilter, offeringFilter]);

  const editStatus = async (row: AttendanceRecord, nextStatus: string) => {
    const confirmed = await confirmDialog({
      title: "แก้ไขสถานะการเข้าเรียน",
      text: `${row.student_code} · ${row.student_name} · ${row.course_code}`,
      confirmText: "ยืนยันการแก้ไข",
      icon: "question",
    });
    if (!confirmed) return;
    // Reason is mandatory on the backend (AttendanceRecordUpdateSerializer).
    const reason = await promptReason("เหตุผลการแก้ไขสถานะ (บันทึกลง Audit Log)");
    if (!reason) return;
    try {
      const { envelope } = await samsRequest({
        url: `/attendance/records/${row.id}/`,
        method: "PATCH",
        data: { status: nextStatus, edit_reason: reason.trim() },
      });
      await toastSuccess(envelope.message);
      await refresh();
    } catch (error) {
      await alertError(
        "แก้ไขสถานะไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    }
  };

  return (
    <AppShell title="รายการเช็คชื่อทั้งหมด">
      {!user && null}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-col gap-1">
          <label htmlFor="status-filter" className="text-xs font-medium text-slate-500">
            สถานะ
          </label>
          <select
            id="status-filter"
            value={status}
            onChange={(e) => {
              setPage(1);
              setStatus(e.target.value);
            }}
            className={`${inputClass} min-w-[160px]`}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>
        <form
          className="flex flex-1 min-w-[240px] items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(searchInput);
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="rec-search" className="text-xs font-medium text-slate-500">
              ค้นหานักศึกษา
            </label>
            <input
              id="rec-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="รหัสนักศึกษา / ชื่อ-นามสกุล…"
              className={inputClass}
            />
          </div>
          <button type="submit" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">
            ค้นหา
          </button>
          <button
            type="button"
            onClick={() => {
              setStatus("");
              setSearchInput("");
              setSearch("");
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            ล้างตัวกรอง
          </button>
        </form>
      </div>

      <DataTable<AttendanceRecord>
        columns={[
          { key: "course_code", label: "รายวิชา" },
          { key: "session_date", label: "วันเรียน", render: (r) => formatThaiDate(r.session_date) },
          { key: "student_code", label: "รหัสนักศึกษา" },
          { key: "student_name", label: "ชื่อ-นามสกุล" },
          { key: "status", label: "สถานะ", render: (r) => <StatusBadge status={r.status} display={r.status_display} /> },
          { key: "checked_in_at", label: "เวลาเช็คชื่อ", render: (r) => formatThaiDateTime(r.checked_in_at) },
          { key: "method_display", label: "วิธีเช็ค" },
          {
            key: "edit_info",
            label: "ผู้แก้ไขล่าสุด",
            render: (r) => (r.edited_by_username ? `${r.edited_by_username}${r.edit_reason ? ` — ${r.edit_reason}` : ""}` : "-"),
          },
        ]}
        rows={rows}
        loading={loading}
        emptyMessage="ยังไม่มีรายการเช็คชื่อที่ตรงกับตัวกรอง"
        renderActions={(row) => (
          <select
            aria-label="แก้ไขสถานะ"
            value={row.status}
            onChange={(e) => void editStatus(row, e.target.value)}
            className="rounded-lg border border-slate-300 px-2 py-1 text-xs"
          >
            {STATUS_OPTIONS.filter((o) => o.value).map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        )}
      />
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />

      <p className="mt-3 text-xs text-slate-500">
        การแก้ไขสถานะต้องระบุเหตุผลและถูกบันทึกลง Audit Log ตามข้อกำหนด (§14.3)
      </p>
    </AppShell>
  );
}
