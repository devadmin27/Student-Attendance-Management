"use client";
/**
 * Shared defs + toolbar actions for the course-offering / enrollment /
 * schedule admin pages. Both /admin/* and /instructor/* routes import these
 * so the two roles manage the same objects with the same forms (backend
 * scopes instructors to the offerings they teach).
 */
import { useState } from "react";
import CrudPage, { type FieldDef } from "@/components/CrudPage";
import { StatusBadge } from "@/components/ui";
import { samsRequest } from "@/lib/api";
import { alertError, toastSuccess } from "@/lib/swal";
import { loadOptions, type Option } from "@/lib/options";
import { formatThaiDateTime } from "@/lib/format";
import type { CourseOffering, Enrollment, ClassSchedule } from "@/lib/types";

// ── shared option lists ────────────────────────────────────────────────

export const OFFERING_STATUS_OPTIONS = [
  { value: "open", label: "เปิดรับลงทะเบียน" },
  { value: "in_progress", label: "กำลังเรียน" },
  { value: "completed", label: "จบภาคเรียนแล้ว" },
  { value: "cancelled", label: "ยกเลิก" },
];

export const ENROLLMENT_STATUS_OPTIONS = [
  { value: "enrolled", label: "กำลังศึกษา" },
  { value: "dropped", label: "ถอนรายวิชา" },
  { value: "completed", label: "จบรายวิชา" },
];

export const WEEKDAY_OPTIONS = [
  { value: "0", label: "จันทร์" },
  { value: "1", label: "อังคาร" },
  { value: "2", label: "พุธ" },
  { value: "3", label: "พฤหัสบดี" },
  { value: "4", label: "ศุกร์" },
  { value: "5", label: "เสาร์" },
  { value: "6", label: "อาทิตย์" },
];

export const SCHEDULE_STATUS_OPTIONS = [
  { value: "planned", label: "กำหนดการ" },
  { value: "active", label: "ใช้งานอยู่" },
  { value: "cancelled", label: "ยกเลิก" },
];

// ── course offerings ───────────────────────────────────────────────────

/** ฟอร์มเปิดสอน: รายวิชาค้นหาด้วยรหัสวิชา + อาจารย์ผู้รับผิดชอบเลือกได้หลายคน */
export const offeringFields: FieldDef[] = [
  {
    name: "course",
    label: "รายวิชา (ค้นหาด้วยรหัสวิชา)",
    type: "select-search",
    required: true,
    optionsKey: "courses",
    placeholder: "พิมพ์รหัสวิชา เช่น AI…",
  },
  { name: "academic_term", label: "ภาคการศึกษา", type: "select", required: true, optionsKey: "academic-terms" },
  {
    name: "instructors",
    label: "อาจารย์ผู้รับผิดชอบ (เลือกได้หลายคน)",
    type: "multiselect",
    optionsKey: "instructors",
    hint: "คนแรกในรายการจะเป็น “อาจารย์หลัก”",
  },
  { name: "class_group", label: "กลุ่มเรียน (ถ้ามี)", type: "select", optionsKey: "class-groups" },
  { name: "status", label: "สถานะ", type: "select", options: OFFERING_STATUS_OPTIONS, defaultValue: "open" },
];

export const offeringColumns = [
  { key: "course_code", label: "รหัสรายวิชา" },
  { key: "course_name", label: "ชื่อรายวิชา" },
  { key: "term_label", label: "ภาคการศึกษา" },
  {
    key: "instructor_names",
    label: "อาจารย์ผู้รับผิดชอบ",
    render: (row: CourseOffering) =>
      (row.instructor_names ?? []).length > 0
        ? (row.instructor_names ?? []).join(", ")
        : (row.instructor_name ?? "-"),
  },
  { key: "enrollment_count", label: "จำนวนลงทะเบียน", className: "tabular-nums" },
  { key: "status", label: "สถานะ", render: (row: CourseOffering) => <StatusBadge status={row.status} /> },
];

export const offeringFilters = [
  { name: "academic_term", label: "ภาคการศึกษา", optionsKey: "academic-terms" as const },
  { name: "course", label: "รายวิชา", optionsKey: "courses" as const },
  { name: "status", label: "สถานะ", options: OFFERING_STATUS_OPTIONS },
];

// ── enrollments ────────────────────────────────────────────────────────

export const enrollmentFields: FieldDef[] = [
  {
    name: "student",
    label: "นักศึกษา (รายคน)",
    type: "select-search",
    required: true,
    optionsKey: "students",
    placeholder: "พิมพ์รหัสนักศึกษา…",
  },
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", type: "select-search", required: true, optionsKey: "course-offerings", placeholder: "พิมพ์รหัสวิชา…" },
  { name: "enrollment_status", label: "สถานะการลงทะเบียน", type: "select", options: ENROLLMENT_STATUS_OPTIONS, defaultValue: "enrolled" },
];

export const enrollmentColumns = [
  { key: "student_code", label: "รหัสนักศึกษา" },
  { key: "student_name", label: "ชื่อ-นามสกุล" },
  { key: "course_code", label: "รายวิชา" },
  { key: "course_name", label: "ชื่อรายวิชา" },
  { key: "enrollment_status", label: "สถานะ", render: (row: Enrollment) => <StatusBadge status={row.enrollment_status} /> },
  { key: "enrolled_at", label: "ลงทะเบียนเมื่อ", render: (row: Enrollment) => formatThaiDateTime(row.enrolled_at) },
];

export const enrollmentFilters = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", optionsKey: "course-offerings" as const },
  { name: "student", label: "นักศึกษา", optionsKey: "students" as const },
  { name: "enrollment_status", label: "สถานะ", options: ENROLLMENT_STATUS_OPTIONS },
];

/** ปุ่ม "ลงทะเบียนแบบกลุ่มเรียน" — POST /enrollments/bulk/ (ทั้งกลุ่มแทนรายคน) */
export function BulkEnrollButton({ refresh }: { refresh: () => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [offering, setOffering] = useState("");
  const [group, setGroup] = useState("");
  const [offOpts, setOffOpts] = useState<Option[]>([]);
  const [grpOpts, setGrpOpts] = useState<Option[]>([]);

  const openModal = async () => {
    setOffering("");
    setGroup("");
    setOpen(true);
    const [o, g] = await Promise.all([
      loadOptions("course-offerings").catch(() => []),
      loadOptions("class-groups").catch(() => []),
    ]);
    setOffOpts(o);
    setGrpOpts(g);
  };

  const submit = async () => {
    if (!offering || !group) {
      await alertError("กรุณาเลือกรายวิชาและกลุ่มเรียน");
      return;
    }
    setSaving(true);
    try {
      const { data } = await samsRequest<{ created: number; skipped: number }>({
        url: "/enrollments/bulk/",
        method: "POST",
        data: { course_offering: offering, class_group: group },
      });
      setOpen(false);
      await toastSuccess(
        `ลงทะเบียนเพิ่ม ${data?.created ?? 0} คน (มีอยู่ก่อนแล้วข้าม ${data?.skipped ?? 0} คน)`,
      );
      refresh();
    } catch (error) {
      await alertError("ลงทะเบียนแบบกลุ่มไม่สำเร็จ", error instanceof Error ? error.message : undefined);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => void openModal()}
        className="ml-2 rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700"
      >
        🏫 ลงทะเบียนแบบกลุ่มเรียน
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => !saving && setOpen(false)} />
          <form
            onSubmit={(e) => {
              e.preventDefault();
              void submit();
            }}
            className="relative z-10 w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="mb-4 text-lg font-semibold text-slate-900">ลงทะเบียนแบบกลุ่มเรียน</h2>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="bulk-group" className="text-sm font-medium text-slate-700">
                  กลุ่มเรียน <span className="text-red-500">*</span>
                </label>
                <select
                  id="bulk-group"
                  required
                  value={group}
                  onChange={(e) => setGroup(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">— เลือกกลุ่มเรียน —</option>
                  {grpOpts.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="bulk-offering" className="text-sm font-medium text-slate-700">
                  รายวิชาที่เปิดสอน <span className="text-red-500">*</span>
                </label>
                <select
                  id="bulk-offering"
                  required
                  value={offering}
                  onChange={(e) => setOffering(e.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none"
                >
                  <option value="">— เลือกรายวิชา —</option>
                  {offOpts.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <span className="text-xs text-slate-400">
                  ระบบจะลงทะเบียนนักศึกษาทุกคนในกลุ่ม (สถานะใช้งานอยู่) เข้ารายวิชานี้ — คนที่ลงแล้วจะถูกข้าม
                </span>
              </div>
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                disabled={saving}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
              >
                ยกเลิก
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
              >
                {saving ? "กำลังลงทะเบียน…" : "ลงทะเบียนทั้งกลุ่ม"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}

// ── class schedules ────────────────────────────────────────────────────

export const scheduleFields: FieldDef[] = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", type: "select-search", required: true, optionsKey: "course-offerings", placeholder: "พิมพ์รหัสวิชา…" },
  { name: "weekday", label: "วันเรียน", type: "select", required: true, options: WEEKDAY_OPTIONS, defaultValue: "0" },
  { name: "start_time", label: "เวลาเริ่มสอน", type: "time", required: true },
  { name: "end_time", label: "เวลาสิ้นสุด", type: "time", required: true },
  { name: "classroom", label: "ห้องเรียน", type: "text", placeholder: "เช่น SC-201" },
  { name: "status", label: "สถานะ", type: "select", options: SCHEDULE_STATUS_OPTIONS, defaultValue: "active" },
];

export const scheduleColumns = [
  { key: "course_code", label: "รายวิชา" },
  { key: "course_name", label: "ชื่อรายวิชา" },
  { key: "term_label", label: "ภาคการศึกษา" },
  {
    key: "weekday_display",
    label: "วันเรียน",
    render: (row: ClassSchedule) =>
      `${row.weekday_display} ${row.start_time.slice(0, 5)}-${row.end_time.slice(0, 5)}`,
  },
  { key: "classroom", label: "ห้อง", render: (row: ClassSchedule) => row.classroom || "-" },
  { key: "status", label: "สถานะ", render: (row: ClassSchedule) => <StatusBadge status={row.status} /> },
];

export const scheduleFilters = [
  { name: "course_offering", label: "รายวิชาที่เปิดสอน", optionsKey: "course-offerings" as const },
  { name: "weekday", label: "วันเรียน", options: WEEKDAY_OPTIONS },
  { name: "status", label: "สถานะ", options: SCHEDULE_STATUS_OPTIONS },
];
