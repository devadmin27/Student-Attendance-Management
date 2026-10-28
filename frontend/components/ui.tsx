"use client";
/** Small shared presentational pieces for SAMS pages. */

export function StatCard({
  label,
  value,
  hint,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: "blue" | "green" | "amber" | "red" | "slate";
}) {
  const tones: Record<string, string> = {
    blue: "border-blue-100 bg-blue-50 text-blue-900",
    green: "border-emerald-100 bg-emerald-50 text-emerald-900",
    amber: "border-amber-100 bg-amber-50 text-amber-900",
    red: "border-red-100 bg-red-50 text-red-900",
    slate: "border-slate-200 bg-white text-slate-900",
  };
  return (
    <div className={`rounded-xl border p-4 shadow-sm ${tones[tone]}`}>
      <div className="text-xs font-medium opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-bold tabular-nums">{value}</div>
      {hint && <div className="mt-1 text-[11px] opacity-70">{hint}</div>}
    </div>
  );
}

const BADGE_TONES: Record<string, string> = {
  present: "bg-emerald-100 text-emerald-800",
  late: "bg-amber-100 text-amber-800",
  absent: "bg-red-100 text-red-800",
  excused: "bg-sky-100 text-sky-800",
  open: "bg-emerald-100 text-emerald-800",
  scheduled: "bg-slate-100 text-slate-700",
  paused: "bg-amber-100 text-amber-800",
  closed: "bg-slate-200 text-slate-800",
  cancelled: "bg-red-100 text-red-800",
  active: "bg-emerald-100 text-emerald-800",
  enrolled: "bg-blue-100 text-blue-800",
  in_progress: "bg-sky-100 text-sky-800",
  completed: "bg-slate-200 text-slate-700",
  dropped: "bg-red-100 text-red-800",
  planned: "bg-slate-100 text-slate-700",
  suspended: "bg-amber-100 text-amber-800",
  inactive: "bg-slate-100 text-slate-600",
};

const THAI_LABELS: Record<string, string> = {
  present: "เข้าเรียน",
  late: "มาสาย",
  absent: "ขาดเรียน",
  excused: "ลากิจ/ลาป่วย",
  open: "เปิดรับเช็คชื่อ",
  scheduled: "กำหนดการ",
  paused: "หยุดชั่วคราว",
  closed: "ปิดแล้ว",
  cancelled: "ยกเลิก",
  active: "ใช้งานอยู่",
  in_progress: "กำลังเรียน",
  completed: "จบแล้ว",
  dropped: "ถอนรายวิชา",
  enrolled: "กำลังศึกษา",
  planned: "กำหนดการ",
  suspended: "ระงับ",
  inactive: "ไม่ใช้งาน",
};

export function StatusBadge({ status, display }: { status: string; display?: string }) {
  const tone = BADGE_TONES[status] ?? "bg-slate-100 text-slate-700";
  const label = display ?? THAI_LABELS[status] ?? status;
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${tone}`}>
      {label}
    </span>
  );
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
      {message}
    </div>
  );
}

export function PageCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5 ${className}`}>
      {children}
    </div>
  );
}
