"use client";
/** Year-level promotion: selected students and whole class groups. */
import { useState } from "react";

import { ApiError, samsRequest } from "@/lib/api";
import { loadOptions, type Option } from "@/lib/options";
import {
  alertError,
  confirmDialog,
  promptReason,
  showBatchSummary,
} from "@/lib/swal";
import type {
  ClassGroup,
  StudentProfile,
  StudentPromotionResult,
} from "@/lib/types";

const YEARS = [1, 2, 3, 4];

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none";

function summaryOf(result: StudentPromotionResult): string {
  return `สำเร็จ ${result.succeeded} รายการ · ข้าม ${result.skipped} รายการ · ไม่สำเร็จ ${result.failed} รายการ`;
}

function detailsOf(result: StudentPromotionResult): string[] {
  return result.results
    .filter((row) => !row.ok || row.skipped)
    .map((row) => `${row.student_code || row.id}: ${row.message || "ไม่สำเร็จ"}`);
}

async function postPromotion(url: string, data: Record<string, unknown>) {
  return samsRequest<StudentPromotionResult>({ url, method: "POST", data });
}

/** Multi-select: promote only the ticked students; class groups stay unchanged. */
export function StudentPromotionActions({
  rows,
  refresh,
  clearSelection,
}: {
  rows: StudentProfile[];
  refresh: () => void;
  clearSelection: () => void;
}) {
  const [busy, setBusy] = useState(false);

  const run = async () => {
    const reason = await promptReason(
      `เลื่อนชั้นนักศึกษาที่เลือก ${rows.length} รายการ`,
      "ระบบจะเลื่อนปีละ 1 ชั้น และไม่เปลี่ยนชั้นปีของกลุ่มเรียน",
    );
    if (reason === null) return;
    const payload = {
      ids: rows.map((row) => row.id),
      expected_years: Object.fromEntries(
        rows.map((row) => [row.id, row.academic_year_level]),
      ),
      reason,
    };
    setBusy(true);
    try {
      const preview = (await postPromotion("/students/promote-selected/", {
        ...payload,
        dry_run: true,
      })).data;
      if (!preview) throw new Error("ระบบไม่ได้รับผลลัพธ์จากเซิร์ฟเวอร์");
      const confirmed = await confirmDialog({
        title: "ยืนยันเลื่อนชั้นที่เลือก",
        text: `${summaryOf(preview)} — เลื่อนปีละ 1 ชั้น ไม่เปลี่ยนชั้นปีของกลุ่มเรียน`,
        confirmText: "ยืนยันเลื่อนชั้น",
      });
      if (!confirmed) return;
      const result = (await postPromotion("/students/promote-selected/", {
        ...payload,
        dry_run: false,
      })).data;
      if (!result) throw new Error("ระบบไม่ได้รับผลลัพธ์จากเซิร์ฟเวอร์");
      await showBatchSummary({
        icon: result.failed > 0 ? "warning" : "success",
        title: result.failed > 0 ? "เลื่อนชั้นเสร็จบางส่วน" : "เลื่อนชั้นสำเร็จ",
        summary: summaryOf(result),
        details: detailsOf(result),
      });
      if (result.succeeded > 0) clearSelection();
      refresh();
    } catch (error) {
      await alertError(
        "เลื่อนชั้นไม่สำเร็จ",
        error instanceof ApiError ? error.message : error instanceof Error ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <button
      type="button"
      onClick={() => void run()}
      disabled={busy}
      className="rounded-lg border border-emerald-300 bg-emerald-100 px-3 py-1.5 text-xs font-medium text-emerald-800 hover:bg-emerald-200 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {busy ? "กำลังดำเนินการ…" : `เลื่อนชั้นที่เลือก (${rows.length})`}
    </button>
  );
}

type GroupChoice = Option & { programId: string; year: number };

async function loadGroupChoices(): Promise<GroupChoice[]> {
  const { data } = await samsRequest<
    { results?: ClassGroup[] } | ClassGroup[]
  >({ url: "/class-groups/", params: { page_size: 100 } });
  const rows = Array.isArray(data) ? data : (data?.results ?? []);
  return rows.map((group) => ({
    value: group.id,
    label: `${group.group_code} · ${group.group_name} · ปี ${group.academic_year_level}`,
    programId: group.program,
    year: group.academic_year_level,
  }));
}

/** Group mode: promote students AND the matching class group(s). */
export function BulkPromoteButton({ refresh }: { refresh: () => void }) {
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [program, setProgram] = useState("");
  const [fromYear, setFromYear] = useState("");
  const [group, setGroup] = useState("");
  const [programs, setPrograms] = useState<Option[]>([]);
  const [groups, setGroups] = useState<GroupChoice[]>([]);

  const openModal = async () => {
    setProgram("");
    setFromYear("");
    setGroup("");
    setOpen(true);
    const [programOptions, groupOptions] = await Promise.all([
      loadOptions("programs").catch(() => []),
      loadGroupChoices().catch(() => []),
    ]);
    setPrograms(programOptions);
    setGroups(groupOptions);
  };

  const visibleGroups = groups.filter(
    (item) =>
      (!program || item.programId === program) &&
      (!fromYear || item.year === Number(fromYear)),
  );

  const submit = async () => {
    if (!program && !group) {
      await alertError("กรุณาเลือกหลักสูตรหรือกลุ่มเรียน");
      return;
    }
    if (program && !fromYear) {
      await alertError("กรุณาเลือกชั้นปีปัจจุบัน");
      return;
    }
    const reason = await promptReason(
      "เลื่อนชั้นทั้งกลุ่มเรียน — ระบุเหตุผล",
      "ระบบจะเลื่อนชั้นปีของนักศึกษาและกลุ่มเรียนที่ตรงเงื่อนไข ปีละ 1 ชั้น",
    );
    if (reason === null) return;
    const payload = {
      program: program || undefined,
      class_group: group || undefined,
      from_year: Number(fromYear),
      reason,
    };
    setSaving(true);
    try {
      const preview = (await postPromotion("/students/promote-group/", {
        ...payload,
        dry_run: true,
      })).data;
      if (!preview) throw new Error("ระบบไม่ได้รับผลลัพธ์จากเซิร์ฟเวอร์");
      const confirmed = await confirmDialog({
        title: "ยืนยันเลื่อนชั้นทั้งกลุ่ม",
        text: `${summaryOf(preview)} — ชั้นปีของกลุ่มเรียนจะเพิ่มขึ้นด้วย`,
        confirmText: "ยืนยันเลื่อนชั้น",
      });
      if (!confirmed) return;
      const result = (await postPromotion("/students/promote-group/", {
        ...payload,
        dry_run: false,
      })).data;
      if (!result) throw new Error("ระบบไม่ได้รับผลลัพธ์จากเซิร์ฟเวอร์");
      await showBatchSummary({
        icon: result.failed > 0 ? "warning" : "success",
        title: result.failed > 0 ? "เลื่อนชั้นเสร็จบางส่วน" : "เลื่อนชั้นสำเร็จ",
        summary: summaryOf(result),
        details: detailsOf(result),
      });
      setOpen(false);
      refresh();
    } catch (error) {
      await alertError(
        "เลื่อนชั้นแบบกลุ่มไม่สำเร็จ",
        error instanceof ApiError ? error.message : error instanceof Error ? error.message : undefined,
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => void openModal()}
        className="ml-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-800"
      >
        🎓 เลื่อนชั้นทั้งกลุ่ม
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => !saving && setOpen(false)}
          />
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
            className="relative z-10 w-full max-w-md rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="mb-4 text-lg font-semibold text-slate-900">
              เลื่อนชั้นทั้งกลุ่มเรียน
            </h2>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="promote-program" className="text-sm font-medium text-slate-700">
                  หลักสูตร
                </label>
                <select
                  id="promote-program"
                  value={program}
                  onChange={(event) => {
                    setProgram(event.target.value);
                    setGroup("");
                  }}
                  className={inputClass}
                >
                  <option value="">— ทุกหลักสูตร (ต้องระบุชั้นปี) —</option>
                  {programs.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="promote-year" className="text-sm font-medium text-slate-700">
                  ชั้นปีปัจจุบัน
                </label>
                <select
                  id="promote-year"
                  value={fromYear}
                  onChange={(event) => {
                    setFromYear(event.target.value);
                    setGroup("");
                  }}
                  className={inputClass}
                >
                  <option value="">— เลือกชั้นปี —</option>
                  {YEARS.map((year) => (
                    <option key={year} value={year}>
                      ปี {year}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1">
                <label htmlFor="promote-group" className="text-sm font-medium text-slate-700">
                  กลุ่มเรียน (เลือกเพื่อจำกัดเฉพาะกลุ่ม)
                </label>
                <select
                  id="promote-group"
                  value={group}
                  onChange={(event) => {
                    const value = event.target.value;
                    setGroup(value);
                    const chosen = groups.find((item) => item.value === value);
                    if (chosen) setFromYear(String(chosen.year));
                  }}
                  className={inputClass}
                >
                  <option value="">— ทุกกลุ่มที่ตรงเงื่อนไข —</option>
                  {visibleGroups.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <span className="text-xs text-slate-400">
                  นักศึกษาที่มีสถานะไม่ใช่ &quot;กำลังศึกษา&quot; หรืออยู่ชั้นปี 4 จะถูกข้าม
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
                {saving ? "กำลังตรวจสอบ…" : "ดูตัวอย่างและยืนยัน"}
              </button>
            </div>
          </form>
        </div>
      )}
    </>
  );
}
