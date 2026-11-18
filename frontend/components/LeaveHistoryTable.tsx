"use client";
/**
 * Shared "ประวัติการลา" table (Column1 การลา · Column2 ลามาแล้ว · Column3
 * ลาครั้งนี้) with two fixed rows: ลาป่วย (วัน) and ลากิจ (วัน).
 *
 * `card` is used on the detail pages and the live form preview;
 * `print` reuses the A4 document's border/font styling and avoids page breaks.
 */
import type { LeaveHistoryRow } from "@/lib/types";

const cardCell = "border border-slate-200 px-3 py-2 text-left text-sm text-slate-800";
const cardHead =
  "border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-semibold text-slate-700";
const printCell = "border border-slate-400 px-2 py-1.5 text-left text-sm";
const printHead =
  "border border-slate-400 px-2 py-1.5 text-left text-sm font-semibold";

interface LeaveHistoryTableProps {
  rows: LeaveHistoryRow[];
  variant?: "card" | "print";
  /** Small helper note, e.g. live-preview status on the create/edit form. */
  caption?: string;
}

export default function LeaveHistoryTable({
  rows,
  variant = "card",
  caption,
}: LeaveHistoryTableProps) {
  const isPrint = variant === "print";
  const cell = isPrint ? printCell : cardCell;
  const head = isPrint ? printHead : cardHead;

  const table = (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr>
          <th className={head}>การลา</th>
          <th className={`${head} text-center`}>ลามาแล้ว</th>
          <th className={`${head} text-center`}>ลาครั้งนี้</th>
        </tr>
      </thead>
      <tbody>
        {(rows ?? []).map((row) => (
          <tr key={row.leave_type}>
            <td className={cell}>{row.label}</td>
            <td className={`${cell} text-center`}>{row.previous_days}</td>
            <td className={`${cell} text-center`}>{row.current_days}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  if (isPrint) {
    return (
      <section className="leave-print-avoid-break mt-4">
        <h2 className="text-sm font-bold">ประวัติการลา</h2>
        <div className="mt-1">{table}</div>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold text-slate-800">ประวัติการลา</h2>
        {caption && <span className="text-xs text-slate-500">{caption}</span>}
      </div>
      <div className="mt-3 overflow-x-auto">{table}</div>
    </section>
  );
}
