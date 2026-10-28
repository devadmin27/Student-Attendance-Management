"use client";
/** Admin dashboard — real numbers from /dashboard/admin/ (spec §7.1). */
import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import AppShell from "@/components/AppShell";
import { StatCard, StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import type { AdminDashboardData } from "@/lib/types";
import { formatThaiDate, formatThaiTime } from "@/lib/format";
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

export default function AdminDashboardPage() {
  const user = useRequireRole(["admin"]);
  const [data, setData] = useState<AdminDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data: payload } = await samsRequest<AdminDashboardData>({ url: "/dashboard/admin/" });
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
    <AppShell title="Dashboard ผู้ดูแลระบบ">
      {!user && null}
      {loading || !data ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดข้อมูลแดชบอร์ด…</p>
      ) : (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="ผู้ใช้ทั้งหมด" value={data.users_total} hint={`ใช้งานอยู่ ${data.users_active} บัญชี`} />
            <StatCard label="นักศึกษา" value={data.students_total} tone="green" />
            <StatCard label="อาจารย์" value={data.instructors_total} tone="amber" />
            <StatCard label="หลักสูตร" value={data.programs_total} />
            <StatCard
              label="รายวิชา"
              value={data.courses_total}
              hint={`เปิดใช้งาน ${data.courses_active} รายการ`}
              tone="slate"
            />
            <StatCard label="การเปิดสอน" value={data.offerings_total} tone="slate" />
            <StatCard
              label="คาบเรียนทั้งหมด"
              value={data.sessions_total}
              hint={`วันนี้ ${data.sessions_today} คาบ · เปิดอยู่ ${data.sessions_open} คาบ`}
              tone="blue"
            />
            <StatCard
              label="รายการเช็คชื่อวันนี้"
              value={data.records_today}
              hint={`7 วันล่าสุด ${data.records_this_week} รายการ`}
              tone="green"
            />
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">
              แนวโน้มการเช็คชื่อรายวัน (14 วันล่าสุด — นับคาบที่ปิดแล้ว)
            </h2>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={data.daily_trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tickFormatter={(v: string) => v.slice(5)} fontSize={11} />
                  <YAxis allowDecimals={false} fontSize={11} />
                  <Tooltip formatter={(value) => [`${value} รายการ`, "เข้าเรียน"]} />
                  <Line type="monotone" dataKey="count" stroke="#2563eb" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-slate-800">สัดส่วนสถานะการเข้าเรียน</h2>
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
              <h2 className="mb-3 text-sm font-semibold text-slate-800">จำนวนนักศึกษาตามหลักสูตร</h2>
              {data.program_students.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">ยังไม่มีนักศึกษาในระบบ</p>
              ) : (
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={data.program_students.filter((p) => p.program)}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="program" fontSize={10} interval={0} height={60} angle={-20} textAnchor="end" />
                      <YAxis allowDecimals={false} fontSize={11} />
                      <Tooltip formatter={(value) => [`${value} คน`, "นักศึกษา"]} />
                      <Bar dataKey="students" fill="#2563eb" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="mb-3 text-sm font-semibold text-slate-800">
              รายวิชาที่มีอัตราการขาดเรียนสูงสุด 5 อันดับ (คาบที่ปิดแล้ว)
            </h2>
            {data.high_absence_courses.length === 0 ? (
              <p className="py-6 text-center text-sm text-slate-500">ยังไม่มีสถิติการขาดเรียน</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500">
                    <tr>
                      <th className="px-2 py-2">รายวิชา</th>
                      <th className="px-2 py-2">รายการทั้งหมด</th>
                      <th className="px-2 py-2">ขาดเรียน</th>
                      <th className="px-2 py-2">อัตราขาดเรียน</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.high_absence_courses.map((c) => (
                      <tr key={c.course_code} className="border-b border-slate-100 last:border-0">
                        <td className="px-2 py-2">
                          <span className="font-medium text-slate-800">{c.course_code}</span>
                          <span className="ml-2 text-slate-500">{c.course_name}</span>
                        </td>
                        <td className="px-2 py-2 tabular-nums">{c.total_records}</td>
                        <td className="px-2 py-2 tabular-nums text-red-600">{c.absent_count}</td>
                        <td className="px-2 py-2 font-semibold tabular-nums text-red-700">
                          {c.absence_rate.toFixed(2)}%
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-500 shadow-sm">
            ข้อมูล ณ {formatThaiDate(new Date())} · {formatThaiTime(new Date())} — คำนวณจากฐานข้อมูลจริง
            <span className="ml-2 inline-flex items-center gap-1">
              สถานะคาบเรียนเปิดอยู่ <StatusBadge status="open" />
            </span>
          </div>
        </div>
      )}
    </AppShell>
  );
}
