"use client";
/**
 * Attendance report panel shared by admin & instructor pages.
 * Filters (term/offering/program/group/student/date range/period) are applied
 * server-side by GET /reports/attendance/; CSV export opens the same filters.
 */
import { useCallback, useEffect, useState } from "react";
import { StatusBadge } from "@/components/ui";
import DataTable from "@/components/DataTable";
import { samsRequest, ApiError } from "@/lib/api";
import { loadOptions, type Option } from "@/lib/options";
import { alertError } from "@/lib/swal";
import type { AttendanceReportData } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

export default function ReportPanel() {
  const [report, setReport] = useState<AttendanceReportData | null>(null);
  const [loading, setLoading] = useState(true);
  const [options, setOptions] = useState<Record<string, Option[]>>({});
  const [filters, setFilters] = useState<Record<string, string>>({});

  const load = useCallback(async (applyFilters: Record<string, string>) => {
    try {
      await Promise.all([
        loadOptions("academic-terms").catch(() => []),
        loadOptions("course-offerings").catch(() => []),
        loadOptions("programs").catch(() => []),
        loadOptions("class-groups").catch(() => []),
      ]).then(([terms, offerings, programs, groups]) => {
        setOptions((prev) => ({ ...prev, "academic-terms": terms, "course-offerings": offerings, programs, "class-groups": groups }));
      });

      const params: Record<string, string> = {};
      for (const [k, v] of Object.entries(applyFilters)) {
        if (v) params[k] = v;
      }
      const { data, envelope } = await samsRequest<AttendanceReportData>({
        url: "/reports/attendance/",
        params,
        method: "GET",
      });
      setReport(data);
      setLoading(false);
      void envelope;
    } catch (error) {
      await alertError("โหลดรายงานไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void (async () => {
      await Promise.resolve(); // yield ก่อน setState (react-hooks/set-state-in-effect)
      await load({});
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const apply = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    await load(filters);
  };

  const exportCsv = () => {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v) params.set(k, v);
    }
    const qs = params.toString();
    const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
    window.open(`${base}/reports/attendance/export/${qs ? `?${qs}` : ""}`, "_blank", "noopener");
  };

  return (
    <div className="space-y-4">
      <form onSubmit={(e) => void apply(e)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">ภาคการศึกษา</label>
            <select
              value={filters.term ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, term: e.target.value }))}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {(options["academic-terms"] ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">รายวิชาที่เปิดสอน</label>
            <select
              value={filters.course_offering ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, course_offering: e.target.value }))}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {(options["course-offerings"] ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">หลักสูตร</label>
            <select
              value={filters.program ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, program: e.target.value }))}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {(options.programs ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">กลุ่มเรียน</label>
            <select
              value={filters.class_group ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, class_group: e.target.value }))}
              className={inputClass}
            >
              <option value="">ทั้งหมด</option>
              {(options["class-groups"] ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">วันที่เริ่มนับ</label>
            <input
              type="date"
              value={filters.date_from ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, date_from: e.target.value }))}
              className={inputClass}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-slate-500">วันสิ้นสุดช่วงนับ</label>
            <input
              type="date"
              value={filters.date_to ?? ""}
              onChange={(e) => setFilters((p) => ({ ...p, date_to: e.target.value }))}
              className={inputClass}
            />
          </div>
        </div>
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={() => {
              setFilters({});
              void (async () => {
                setLoading(true);
                await load({});
              })();
            }}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            ล้างตัวกรอง
          </button>
          <button type="submit" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">
            แสดงรายงาน
          </button>
          <button
            type="button"
            onClick={exportCsv}
            disabled={!report || report.rows.length === 0}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            ⤓ ส่งออก CSV (ป้องกัน Formula Injection)
          </button>
        </div>
      </form>

      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังคำนวณรายงานจากฐานข้อมูลจริง…</p>
      ) : !report ? (
        <p className="text-sm text-slate-500">ไม่มีข้อมูลรายงาน</p>
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            <span className="font-medium">สูตร:</span>
            <code className="rounded bg-white px-2 py-1 text-xs">{report.formula}</code>
            <span className="ml-auto text-xs text-blue-700">{report.note}</span>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm shadow-sm">
            คาบที่นับอยู่ในรายงาน: <strong className="tabular-nums">{report.total_closed_sessions}</strong> คาบ (ปิดแล้วเท่านั้น)
          </div>
          <DataTable<{
            id: string;
            student_code: string;
            student_name: string;
            present: number;
            late: number;
            absent: number;
            excused: number;
            eligible_sessions: number;
            attendance_rate: number;
          }>
            columns={[
              { key: "student_code", label: "รหัสนักศึกษา" },
              { key: "student_name", label: "ชื่อ-นามสกุล" },
              { key: "present", label: "เข้าเรียน", className: "tabular-nums" },
              { key: "late", label: "มาสาย", className: "tabular-nums" },
              { key: "absent", label: "ขาดเรียน", className: "tabular-nums" },
              { key: "excused", label: "ลา", className: "tabular-nums" },
              { key: "eligible_sessions", label: "คาบที่นับ", className: "tabular-nums" },
              {
                key: "rate-drop",
                label: "อัตราการเข้าเรียน",
                className: "tabular-nums",
                render: (row) => {
                  const tone =
                    row.attendance_rate >= 80
                      ? "bg-emerald-100 text-emerald-800"
                      : row.attendance_rate >= 60
                        ? "bg-amber-100 text-amber-800"
                        : "bg-red-100 text-red-800";
                  return (
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${tone}`}>
                      {row.attendance_rate.toFixed(2)}%
                    </span>
                  );
                },
              },
              {
                key: "badge",
                label: "ภาระเช็คชื่อ",
                render: (row) =>
                  row.eligible_sessions === 0 ? (
                    <StatusBadge status="inactive" display="ไม่มีข้อมูล" />
                  ) : row.attendance_rate >= 80 ? (
                    <StatusBadge status="present" />
                  ) : row.attendance_rate >= 60 ? (
                    <StatusBadge status="late" display="ระวังขาดเรียน" />
                  ) : (
                    <StatusBadge status="absent" />
                  ),
              },
            ]}
            rows={
              report.rows.map((r) => ({
                ...r,
                id: r.student_id,
              })) ?? []
            }
            emptyMessage="ยังไม่มีรายการ — ลองปรับช่วงวันที่หรือรายวิชาที่เลือก"
          />
        </>
      )}
    </div>
  );
}
