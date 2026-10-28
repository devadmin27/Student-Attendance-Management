"use client";
/** Student weekly timetable (dashboard schedules payload). */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { EmptyState } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import type { StudentDashboardData } from "@/lib/types";

const DAY_THAI = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"];
const DAY_ORDER = [0, 1, 2, 3, 4, 5, 6];

export default function StudentSchedulePage() {
  const user = useRequireRole(["student"]);
  const [schedules, setSchedules] = useState<StudentDashboardData["schedules"]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<StudentDashboardData>({ url: "/dashboard/student/" });
        if (!cancelled) setSchedules(data?.schedules ?? []);
      } catch (error) {
        if (!cancelled) {
          await alertError("โหลดตารางเรียนไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = DAY_ORDER.map((day) => ({
    day,
    items: schedules.filter((s) => s.weekday === day).sort((a, b) => a.start_time.localeCompare(b.start_time)),
  }));

  return (
    <AppShell title="ตารางเรียนของฉัน">
      {!user && null}
      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดตารางเรียน…</p>
      ) : schedules.length === 0 ? (
        <EmptyState message="ยังไม่มีตารางเรียนที่ใช้งานอยู่ในภาคนี้" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {grouped.map(({ day, items }) => (
            <div key={day} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-sm font-semibold text-slate-800">{DAY_THAI[day]}</h2>
              {items.length === 0 ? (
                <p className="text-xs text-slate-400">ไม่มีคาบเรียน</p>
              ) : (
                <ul className="space-y-2">
                  {items.map((s) => (
                    <li key={s.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-sm">
                      <div className="font-medium text-slate-800">
                        {s.course_code} — {s.course_name}
                      </div>
                      <div className="mt-0.5 text-xs text-slate-500">
                        {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)} · ห้อง {s.classroom || "-"}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
