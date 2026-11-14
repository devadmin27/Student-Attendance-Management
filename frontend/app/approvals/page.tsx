"use client";
/**
 * Approval inbox (Phase 2).
 *
 * Instructors see only requests where they are the assignee of the step that
 * is currently pending; admins see every in-flight request (documented
 * override path). Scope is enforced by /leave-approvals/, never here.
 */
import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { LeaveRequest, LeaveType } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const STATUS_OPTIONS = [
  { value: "pending_advisor_review", label: "รอความเห็นอาจารย์ที่ปรึกษา" },
  { value: "pending_program_head_review", label: "รอความเห็นหัวหน้าหน่วยหลักสูตร" },
  { value: "pending_final_approval", label: "รอผู้มีอำนาจอนุมัติ" },
];

const LEAVE_TYPE_OPTIONS: { value: LeaveType; label: string }[] = [
  { value: "sick", label: "ลาป่วย" },
  { value: "personal", label: "ลากิจ" },
  { value: "other", label: "อื่น ๆ" },
];

export default function ApprovalsPage() {
  const user = useRequireRole(["instructor", "admin"]);
  const [rows, setRows] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [statusFilter, setStatusFilter] = useState("");
  const [leaveType, setLeaveType] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = {
          page,
          page_size: 20,
          ordering: "submitted_at",
        };
        if (statusFilter) params.status = statusFilter;
        if (leaveType) params.leave_type = leaveType;
        if (search.trim()) params.search = search.trim();
        const { data, envelope } = await samsRequest<LeaveRequest[]>({
          url: "/leave-approvals/",
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
            "โหลดคิวอนุมัติไม่สำเร็จ",
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
  }, [page, statusFilter, leaveType, search]);

  return (
    <AppShell title="คิวพิจารณาใบลา">
      {!user && null}
      <div className="mb-4 space-y-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <p className="text-xs text-slate-500">
          {user?.role === "admin"
            ? "ผู้ดูแลระบบเห็นคำร้องที่อยู่ระหว่างการพิจารณาทั้งหมด และใช้สิทธิ์อนุมัติแทนได้จากหน้ารายละเอียด"
            : "แสดงเฉพาะคำร้องที่ถึงขั้นตอนของคุณใน Workflow (อาจารย์ที่ปรึกษา → หัวหน้าหน่วยหลักสูตร → ผู้มีอำนาจอนุมัติ)"}
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label
              htmlFor="approval-status"
              className="mb-1 block text-xs font-medium text-slate-500"
            >
              ขั้นตอนที่รอ
            </label>
            <select
              id="approval-status"
              value={statusFilter}
              onChange={(e) => {
                setPage(1);
                setStatusFilter(e.target.value);
              }}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {STATUS_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label
              htmlFor="approval-type"
              className="mb-1 block text-xs font-medium text-slate-500"
            >
              ประเภทการลา
            </label>
            <select
              id="approval-type"
              value={leaveType}
              onChange={(e) => {
                setPage(1);
                setLeaveType(e.target.value);
              }}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {LEAVE_TYPE_OPTIONS.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
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
            <label
              htmlFor="approval-search"
              className="mb-1 block text-xs font-medium text-slate-500"
            >
              ค้นหานักศึกษาหรือเหตุผล
            </label>
            <input
              id="approval-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="รหัสนักศึกษา ชื่อ หรือเหตุผลการลา"
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
              setStatusFilter("");
              setLeaveType("");
              setSearchInput("");
              setSearch("");
              setPage(1);
            }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            ล้างตัวกรอง
          </button>
          <span className="ml-auto text-xs text-slate-500">
            ทั้งหมด {count} รายการ
          </span>
        </form>
      </div>

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
            key: "leave",
            label: "ช่วงที่ลา",
            render: (row) => (
              <div>
                <div>
                  {formatThaiDate(row.start_date)} — {formatThaiDate(row.end_date)}
                </div>
                <div className="text-xs text-slate-500">
                  {row.leave_type_display} · {row.total_days} วัน
                </div>
              </div>
            ),
          },
          {
            key: "step",
            label: "ขั้นตอนปัจจุบัน",
            render: (row) => (
              <div>
                <StatusBadge status={row.status} display={row.status_display} />
                {row.current_step && (
                  <div className="mt-1 text-xs text-slate-500">
                    {row.current_step.role_type_display} ·{" "}
                    {row.current_step.assignee_name ??
                      row.current_step.assignee_username ??
                      "ยังไม่กำหนดผู้รับผิดชอบ"}
                  </div>
                )}
              </div>
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
        emptyMessage="ไม่มีคำร้องที่รอการพิจารณาของคุณ"
        renderActions={(row) => (
          <Link
            href={`/approvals/${row.id}`}
            className="rounded-lg bg-blue-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-blue-800"
          >
            เปิดพิจารณา
          </Link>
        )}
      />
      <PaginationControls
        page={page}
        pages={pages}
        count={count}
        onChange={setPage}
      />
    </AppShell>
  );
}
