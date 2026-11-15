"use client";
/** Student leave requests — list, status filter, pagination. */
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
  { value: "pending_advisor_review", label: "รออาจารย์ที่ปรึกษา" },
  { value: "pending_program_head_review", label: "รอหัวหน้าหน่วยหลักสูตร" },
  { value: "pending_final_approval", label: "รอผู้มีอำนาจอนุมัติ" },
  { value: "approved", label: "อนุมัติแล้ว" },
  { value: "rejected", label: "ไม่อนุมัติ" },
  { value: "returned", label: "ส่งกลับเพื่อแก้ไข" },
  { value: "cancelled", label: "ยกเลิกคำร้อง" },
];

export default function StudentLeavesPage() {
  const user = useRequireRole(["student"]);
  const [rows, setRows] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page, page_size: 20 };
        if (statusFilter) params.status = statusFilter;
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
            "โหลดรายการใบลาไม่สำเร็จ",
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
  }, [page, statusFilter]);

  return (
    <AppShell title="ใบลาของฉัน">
      {!user && null}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Link
          href="/student/leaves/new"
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          + ยื่นใบลาใหม่
        </Link>
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
        <span className="ml-auto text-xs text-slate-500">ทั้งหมด {count} คำร้อง</span>
      </div>

      {!loading && rows.length === 0 ? (
        <EmptyState message="ยังไม่มีคำร้องลา — เริ่มยื่นใบลาได้จากปุ่มด้านบน" />
      ) : (
        <DataTable<LeaveRequest>
          columns={[
            {
              key: "dates",
              label: "ช่วงที่ลา",
              render: (row) =>
                `${formatThaiDate(row.start_date)} — ${formatThaiDate(row.end_date)}`,
            },
            { key: "leave_type_display", label: "ประเภท" },
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
              href={`/student/leaves/${row.id}`}
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
