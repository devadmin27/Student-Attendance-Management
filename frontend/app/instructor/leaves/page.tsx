"use client";
/** Instructor course inbox — leave requests for offerings they teach. */
import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { LeaveCourseInboxItem } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const REVIEW_OPTIONS = [
  { value: "pending", label: "รอการพิจารณา" },
  { value: "reviewed", label: "ให้ความเห็นแล้ว" },
  { value: "acknowledged", label: "รับทราบ" },
  { value: "rejected", label: "ไม่เห็นด้วย" },
];

const REQUEST_STATUS_OPTIONS = [
  { value: "submitted", label: "ส่งคำร้องแล้ว" },
  { value: "cancelled", label: "ยกเลิกคำร้อง" },
];

export default function InstructorLeavesPage() {
  const user = useRequireRole(["instructor"]);
  const [rows, setRows] = useState<LeaveCourseInboxItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [reviewStatus, setReviewStatus] = useState("");
  const [requestStatus, setRequestStatus] = useState("");
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
        if (reviewStatus) params.review_status = reviewStatus;
        if (requestStatus) params.leave_request__status = requestStatus;
        if (dateFrom) params.leave_request__start_date__gte = dateFrom;
        if (dateTo) params.leave_request__start_date__lte = dateTo;
        if (search.trim()) params.search = search.trim();
        const { data, envelope } = await samsRequest<LeaveCourseInboxItem[]>({
          url: "/leave-courses/",
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
            "โหลดคำร้องลาไม่สำเร็จ",
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
  }, [page, reviewStatus, requestStatus, dateFrom, dateTo, search]);

  return (
    <AppShell title="คำร้องลาในรายวิชาที่ฉันสอน">
      {!user && null}
      <div className="mb-4 space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label htmlFor="review-status" className="mb-1 block text-xs font-medium text-slate-500">
              สถานะการพิจารณารายวิชา
            </label>
            <select
              id="review-status"
              value={reviewStatus}
              onChange={(e) => {
                setPage(1);
                setReviewStatus(e.target.value);
              }}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {REVIEW_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="request-status" className="mb-1 block text-xs font-medium text-slate-500">
              สถานะคำร้องหลัก
            </label>
            <select
              id="request-status"
              value={requestStatus}
              onChange={(e) => {
                setPage(1);
                setRequestStatus(e.target.value);
              }}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {REQUEST_STATUS_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="date-from" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่เริ่มลา (จาก)
            </label>
            <input
              id="date-from"
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
            <label htmlFor="date-to" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่เริ่มลา (ถึง)
            </label>
            <input
              id="date-to"
              type="date"
              value={dateTo}
              onChange={(e) => {
                setPage(1);
                setDateTo(e.target.value);
              }}
              className={inputClass}
            />
          </div>
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
            <label htmlFor="leave-search" className="mb-1 block text-xs font-medium text-slate-500">
              ค้นหานักศึกษาหรือรายวิชา
            </label>
            <input
              id="leave-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="รหัสนักศึกษา ชื่อ หรือรหัสวิชา"
              className={inputClass}
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
              setReviewStatus("");
              setRequestStatus("");
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
          <span className="ml-auto text-xs text-slate-500">ทั้งหมด {count} รายการ</span>
        </form>
      </div>

      <DataTable<LeaveCourseInboxItem>
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
            key: "course",
            label: "รายวิชา",
            render: (row) => (
              <div>
                <div className="text-slate-800">{row.course_code}</div>
                <div className="text-xs text-slate-500">{row.course_name}</div>
              </div>
            ),
          },
          {
            key: "leave",
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
            key: "review_status",
            label: "การพิจารณารายวิชา",
            render: (row) => (
              <StatusBadge
                status={row.review_status}
                display={row.review_status_display}
              />
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
        emptyMessage="ยังไม่มีคำร้องลาที่ตรงกับตัวกรอง"
        renderActions={(row) => (
          <Link
            href={`/instructor/leaves/${row.id}`}
            className="rounded-lg bg-blue-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-800"
          >
            ดู / พิจารณา
          </Link>
        )}
      />
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />
    </AppShell>
  );
}
