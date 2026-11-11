"use client";
/** Admin read-only browser for student leave requests. */
import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { EmptyState, StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { LeaveRequest, LeaveRequestStatus } from "@/lib/types";

const inputClass =
  "rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const STATUS_OPTIONS: { value: LeaveRequestStatus; label: string }[] = [
  { value: "draft", label: "แบบร่าง" },
  { value: "submitted", label: "ส่งคำร้องแล้ว" },
  { value: "cancelled", label: "ยกเลิกคำร้อง" },
];

export default function AdminLeavesPage() {
  const user = useRequireRole(["admin"]);
  const [rows, setRows] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page, page_size: 20 };
        if (statusFilter) params.status = statusFilter;
        if (dateFrom) params.start_date__gte = dateFrom;
        if (dateTo) params.start_date__lte = dateTo;
        if (search.trim()) params.search = search.trim();
        const { data, envelope } = await samsRequest<LeaveRequest[]>({
          url: "/leave-requests/",
          params,
        });
        if (cancelled) return;
        setRows(data ?? []);
        setPages(envelope.pagination?.pages ?? 1);
        setCount(envelope.pagination?.count ?? (data?.length ?? 0));
      } catch (error) {
        if (!cancelled) {
          setRows([]);
          await alertError(
            "โหลดรายการคำร้องลาไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, statusFilter, dateFrom, dateTo, search]);

  return (
    <AppShell title="คำร้องลานักศึกษา">
      {!user && null}
      <div className="mb-4 space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <select
            value={statusFilter}
            onChange={(e) => {
              setPage(1);
              setStatusFilter(e.target.value);
            }}
            className={inputClass}
            aria-label="กรองสถานะคำร้อง"
          >
            <option value="">ทุกสถานะ</option>
            {STATUS_OPTIONS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
          <div>
            <label htmlFor="admin-date-from" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่เริ่มลา (จาก)
            </label>
            <input
              id="admin-date-from"
              type="date"
              value={dateFrom}
              onChange={(e) => {
                setPage(1);
                setDateFrom(e.target.value);
              }}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="admin-date-to" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่เริ่มลา (ถึง)
            </label>
            <input
              id="admin-date-to"
              type="date"
              value={dateTo}
              onChange={(e) => {
                setPage(1);
                setDateTo(e.target.value);
              }}
              className={inputClass}
            />
          </div>
          <span className="ml-auto text-xs text-slate-500">ทั้งหมด {count} คำร้อง</span>
        </div>
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(searchInput.trim());
          }}
        >
          <div className="min-w-[220px] flex-1">
            <label htmlFor="admin-leave-search" className="mb-1 block text-xs font-medium text-slate-500">
              ค้นหานักศึกษา
            </label>
            <input
              id="admin-leave-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="รหัสนักศึกษา หรือชื่อ-นามสกุล"
              className={`${inputClass} w-full`}
            />
          </div>
          <button
            type="submit"
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
          >
            ค้นหา
          </button>
          <button
            type="button"
            onClick={() => {
              setStatusFilter("");
              setDateFrom("");
              setDateTo("");
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

      {!loading && rows.length === 0 ? (
        <EmptyState message="ไม่พบคำร้องลาที่ตรงกับตัวกรอง" />
      ) : (
        <DataTable<LeaveRequest>
          columns={[
            {
              key: "student",
              label: "นักศึกษา",
              render: (row) => (
                <div>
                  <div className="font-medium text-slate-800">{row.student_code}</div>
                  <div className="text-xs text-slate-500">{row.student_name}</div>
                </div>
              ),
            },
            {
              key: "dates",
              label: "ช่วงที่ลา",
              render: (row) => (
                <div>
                  <div>
                    {formatThaiDate(row.start_date)} — {formatThaiDate(row.end_date)}
                  </div>
                  <div className="text-xs text-slate-500">{row.leave_type_display}</div>
                </div>
              ),
            },
            {
              key: "courses",
              label: "รายวิชา",
              render: (row) => (
                <span className="text-xs text-slate-600">
                  {row.courses.length > 0
                    ? row.courses.map((course) => course.course_code).join(", ")
                    : "-"}
                </span>
              ),
            },
            {
              key: "status",
              label: "สถานะคำร้อง",
              render: (row) => (
                <StatusBadge status={row.status} display={row.status_display} />
              ),
            },
            {
              key: "submitted_at",
              label: "ส่งเมื่อ",
              render: (row) =>
                row.submitted_at ? formatThaiDateTime(row.submitted_at) : "-",
            },
          ]}
          rows={rows}
          loading={loading}
          emptyMessage="ไม่มีคำร้องที่ตรงกับตัวกรอง"
          renderActions={(row) => (
            <Link
              href={`/admin/leaves/${row.id}`}
              className="rounded-lg bg-blue-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-800"
            >
              ดูรายละเอียด
            </Link>
          )}
        />
      )}
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />
    </AppShell>
  );
}
