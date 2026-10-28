"use client";
/** Instructor dashboard — own assignments only (spec §7.1). */
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import AppShell from "@/components/AppShell";
import { StatCard, StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import type { InstructorDashboardData } from "@/lib/types";
import { alertError } from "@/lib/swal";

const STATUS_COLORS: Record<string, string> = {
  present: "#10b981",
  late: "#f59e0b",
  absent: "#ef4444",
  excused: "#38bdf8",
};

const STATUS_THAI: Record<string, string> = {
  present: "เข้าเรียน",
  late: "มาสาย",
  absent: "ขาดเรียน",
  excused: "ลากิจ",
};

export default function InstructorDashboardPage() {
  const user = useRequireRole(["instructor"]);
  const [data, setData] = useState<InstructorDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data: payload } = await samsRequest<InstructorDashboardData>({ url: "/dashboard/instructor/" });
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

  const pieData = Object.entries(data?.status_breakdown ?? {}).map(([status, value]) => ({
    name: STATUS_THAI[status] ?? status,
    key: status,
    value: Number(value) || 0,
  }));

  return (
    <AppShell title="Dashboard อาจารย์">
      {!user && null}
      {loading || !data ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดข้อมูลแดชบอร์ด…</p>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="คาบที่มีสอนวันนี้" value={data.sessions_today} tone="blue" />
            <StatCard label="รายวิชาที่รับผิดชอบ" value={data.offerings.length} />
            <StatCard label="รายการเช็คชื่อทั้งหมด" value={data.total_records} tone="slate" />
            <StatCard label="ผู้ขาดเรียน (สะสม)" value={data.total_absent} tone="red" />
          </div>

          {data.open_session_id && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
              <div className="text-sm text-emerald-900">
                ขณะนี้มีคาบที่ <strong>เปิด/หยุดชั่วคราว</strong> อยู่ — เข้าไปควบคุมคาบเรียนได้เลย
              </div>
              <Link
                href={`/instructor/attendance/${data.open_session_id}`}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
              >
                เข้าควบคุมคาบเรียน →
              </Link>
            </div>
          )}

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-slate-800">สัดส่วนสถานะการเข้าเรียน (รายวิชาของฉัน)</h2>
              {pieData.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">ยังไม่มีรายการเช็คชื่อ</p>
              ) : (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={pieData} dataKey="value" nameKey="name" innerRadius={50} outerRadius={90}>
                        {pieData.map((entry) => (
                          <Cell key={entry.key} fill={STATUS_COLORS[entry.key] ?? "#94a3b8"} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(value) => [`${value} รายการ`, "จำนวน"]} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-slate-800">รายวิชาที่รับผิดชอบ</h2>
              {data.offerings.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">ยังไม่มีรายวิชาที่รับผิดชอบในภาคนี้</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="border-b border-slate-200 text-xs text-slate-500">
                      <tr>
                        <th className="px-2 py-2">รายวิชา</th>
                        <th className="px-2 py-2">ภาค</th>
                        <th className="px-2 py-2">ลงทะเบียน</th>
                        <th className="px-2 py-2">สถานะ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.offerings.map((o) => (
                        <tr key={o.id} className="border-b border-slate-100 last:border-0">
                          <td className="px-2 py-2">
                            <span className="font-medium text-slate-800">{o.course_code}</span>
                            <span className="ml-2 text-slate-500">{o.course_name}</span>
                          </td>
                          <td className="px-2 py-2">{o.term}</td>
                          <td className="px-2 py-2 tabular-nums">{o.enrolled}</td>
                          <td className="px-2 py-2">
                            <StatusBadge status={o.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </AppShell>
  );
}
