"use client";
/** Student own attendance history (GET /attendance/my-history/). */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { EmptyState, StatCard, StatusBadge } from "@/components/ui";
import DataTable from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { AttendanceRecord, AttendanceStatus } from "@/lib/types";

interface MyHistoryRow extends AttendanceRecord {
  id: string;
}

function countBy(list: MyHistoryRow[]): Record<AttendanceStatus, number> {
  const counts: Record<AttendanceStatus, number> = { present: 0, late: 0, absent: 0, excused: 0 };
  for (const r of list) counts[r.status] = (counts[r.status] ?? 0) + 1;
  return counts;
}

export default function StudentHistoryPage() {
  const user = useRequireRole(["student"]);
  const [rows, setRows] = useState<MyHistoryRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<MyHistoryRow[]>({ url: "/attendance/my-history/" });
        if (!cancelled) setRows(data ?? []);
      } catch (error) {
        if (!cancelled) {
          await alertError("โหลดประวัติไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const counts = countBy(rows);

  return (
    <AppShell title="ประวัติการเช็คชื่อของฉัน">
      {!user && null}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatCard label="เข้าเรียน" value={counts.present} tone="green" />
        <StatCard label="มาสาย" value={counts.late} tone="amber" />
        <StatCard label="ขาดเรียน" value={counts.absent} tone="red" />
        <StatCard label="ลา/ได้รับอนุญาต" value={counts.excused} tone="blue" />
      </div>

      <div className="mt-4">
        {loading ? (
          <p className="animate-pulse text-slate-500">กำลังโหลดประวัติ…</p>
        ) : rows.length === 0 ? (
          <EmptyState message="ยังไม่มีประวัติการเช็คชื่อ" />
        ) : (
          <DataTable<MyHistoryRow>
            columns={[
              { key: "course_code", label: "รายวิชา" },
              { key: "session_date", label: "วันที่เรียน", render: (r) => formatThaiDate(r.session_date) },
              { key: "status", label: "สถานะ", render: (r) => <StatusBadge status={r.status} display={r.status_display} /> },
              {
                key: "checked_in_at",
                label: "เวลาที่เช็คชื่อ",
                render: (r) => (r.status === "absent" ? "-" : formatThaiDateTime(r.checked_in_at)),
              },
              { key: "method_display", label: "วิธี" },
              {
                key: "edit_reason",
                label: "ถูกแก้ไขโดย",
                render: (r) =>
                  r.edited_by_username
                    ? `${r.edited_by_username}${r.edit_reason ? ` — เหตุผล: ${r.edit_reason}` : ""}`
                    : "-",
              },
            ]}
            rows={rows}
            emptyMessage="ยังไม่มีรายการ"
          />
        )}
      </div>
    </AppShell>
  );
}
