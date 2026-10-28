"use client";
/** Student dashboard — own data only (spec §7.1). */
import Link from "next/link";
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { StatCard, StatusBadge, EmptyState, PageCard } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiTime } from "@/lib/format";
import type { StudentDashboardData } from "@/lib/types";
import { alertError } from "@/lib/swal";

export default function StudentDashboardPage() {
  const user = useRequireRole(["student"]);
  const [data, setData] = useState<StudentDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data: payload } = await samsRequest<StudentDashboardData>({ url: "/dashboard/student/" });
        if (!cancelled) setData(payload);
      } catch (error) {
        if (!cancelled) {
          await alertError("โหลดแดชบอร์ดไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell title="Dashboard นักศึกษา">
      {!user && null}
      {loading || !data ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดข้อมูลของคุณ…</p>
      ) : (
        <div className="space-y-5">
          <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900">
            {data.profile ? (
              <>
                สวัสดี <strong>{data.profile.first_name} {data.profile.last_name}</strong> ({data.profile.student_code})
                {data.current_term && <span className="ml-2 text-blue-700">ภาคการศึกษาปัจจุบัน: {data.current_term}</span>}
              </>
            ) : (
              "ไม่พบโปรไฟล์นักศึกษา — กรุณาติดต่อผู้ดูแลระบบ"
            )}
          </div>

          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="เข้าเรียน (present)" value={data.statistics.present} tone="green" />
            <StatCard label="มาสาย (late)" value={data.statistics.late} tone="amber" />
            <StatCard label="ขาดเรียน (absent)" value={data.statistics.absent} tone="red" />
            <StatCard label="ลากิจ/ลาป่วย (excused)" value={data.statistics.excused} tone="blue" />
          </div>

          <div className="flex flex-wrap gap-3">
            <Link
              href="/student/scan"
              className="rounded-xl bg-blue-700 px-6 py-3 font-medium text-white shadow hover:bg-blue-800"
            >
              📷 สแกน QR เข้าเรียน
            </Link>
            <Link
              href="/student/schedule"
              className="rounded-xl border border-blue-200 bg-white px-6 py-3 font-medium text-blue-800 shadow-sm hover:bg-blue-50"
            >
              ⏰ ดูตารางเรียนวันนี้
            </Link>
          </div>

          <PageCard>
            <h2 className="mb-3 text-sm font-semibold text-slate-800">รายวิชาที่ลงทะเบียน ({data.courses.length})</h2>
            {data.courses.length === 0 ? (
              <EmptyState message="ยังไม่มีรายวิชาที่ลงทะเบียนในภาคนี้" />
            ) : (
              <ul className="grid gap-2 md:grid-cols-2">
                {data.courses.map((course) => (
                  <li key={course.id} className="rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm">
                    <div className="font-medium text-slate-800">
                      {course.course_code} — {course.course_name}
                    </div>
                    <div className="text-xs text-slate-500">ภาคการศึกษา {course.term}</div>
                  </li>
                ))}
              </ul>
            )}
          </PageCard>

          <PageCard>
            <h2 className="mb-3 text-sm font-semibold text-slate-800">รายการเช็คชื่อล่าสุด</h2>
            {data.recent_records.length === 0 ? (
              <EmptyState message="ยังไม่มีประวัติการเช็คชื่อ" />
            ) : (
              <ul className="space-y-2">
                {data.recent_records.map((record, index) => (
                  <li
                    key={`${record.course_code}-${record.checked_in_at}-${index}`}
                    className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 p-3 text-sm"
                  >
                    <span className="font-medium text-slate-800">{record.course_code}</span>
                    <span className="text-slate-500">{formatThaiDate(record.session_date)}</span>
                    <StatusBadge status={record.status} />
                    <span className="ml-auto text-xs text-slate-500">
                      {record.checked_in_at ? formatThaiTime(record.checked_in_at) : "-"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </PageCard>
        </div>
      )}
    </AppShell>
  );
}
