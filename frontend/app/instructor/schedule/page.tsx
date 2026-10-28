"use client";
/** Instructor weekly teaching timetable (class-schedules are instructor-visible). */
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import DataTable from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import { useEffect, useMemo, useState } from "react";
import type { ClassSchedule } from "@/lib/types";

const DAY_ORDER = [0, 1, 2, 3, 4, 5, 6];

export default function InstructorSchedulePage() {
  const user = useRequireRole(["instructor"]);
  const [rows, setRows] = useState<ClassSchedule[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<ClassSchedule[]>({
          url: "/class-schedules/",
          params: { status: "active", page_size: 100 },
        });
        if (cancelled) return;
        setRows(data ?? []);
      } catch (error) {
        if (!cancelled) {
          setRows([]);
          await alertError("โหลดตารางสอนไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const grouped = useMemo(() => {
    const byDay = new Map<number, ClassSchedule[]>();
    for (const row of rows) {
      const list = byDay.get(row.weekday) ?? [];
      list.push(row);
      byDay.set(row.weekday, list);
    }
    for (const list of byDay.values()) {
      list.sort((a, b) => a.start_time.localeCompare(b.start_time));
    }
    return DAY_ORDER.map((day) => ({ day, items: byDay.get(day) ?? [] }));
  }, [rows]);

  return (
    <AppShell title="ตารางสอนประจำสัปดาห์">
      {!user && null}
      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดตารางสอน…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          ยังไม่มีสล็อตตารางสอนที่ใช้งานอยู่
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {grouped.map(({ day, items }) => (
            <div key={day} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-sm font-semibold text-slate-800">
                {items[0]?.weekday_display ?? ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"][day]}
              </h2>
              {items.length === 0 ? (
                <p className="text-xs text-slate-400">ไม่มีคาบสอน</p>
              ) : (
                <ul className="space-y-2">
                  {items.map((s) => (
                    <li key={s.id} className="rounded-lg border border-slate-100 bg-slate-50 p-2.5 text-sm">
                      <div className="font-medium text-slate-800">
                        {s.course_code} — {s.course_name}
                      </div>
                      <div className="mt-0.5 text-xs text-slate-500">
                        {s.start_time.slice(0, 5)} – {s.end_time.slice(0, 5)} · ห้อง {s.classroom || "-"} · {s.term_label}
                        <span className="ml-2">
                          <StatusBadge status={s.status} />
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-800">ตารางเรียนทั้งหมด (ตารางข้อมูล)</h2>
        <DataTable<ClassSchedule>
          columns={[
            { key: "course_code", label: "รายวิชา" },
            { key: "course_name", label: "ชื่อรายวิชา" },
            { key: "term_label", label: "ภาค" },
            { key: "weekday_display", label: "วัน" },
            { key: "time", label: "เวลา", render: (r) => `${r.start_time.slice(0, 5)} – ${r.end_time.slice(0, 5)}` },
            { key: "classroom", label: "ห้อง", render: (r) => r.classroom || "-" },
            { key: "status", label: "สถานะ", render: (r) => <StatusBadge status={r.status} /> },
          ]}
          rows={rows}
          loading={loading}
          emptyMessage="ยังไม่มีตารางเรียน"
        />
      </div>
    </AppShell>
  );
}
