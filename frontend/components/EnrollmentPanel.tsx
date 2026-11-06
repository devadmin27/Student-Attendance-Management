"use client";
/**
 * Shared enrollment management (admin + instructor).
 *
 * Enrollment corrections are deliberately two different operations:
 * - ถอน (withdraw): keep the row + every attendance record, set status dropped
 * - ลบ (delete): only for mistaken rows with zero attendance history
 * The backend enforces the same rules, so the UI can never silently detach a
 * student's check-in history from the course.
 */
import { useState } from "react";

import CrudPage from "@/components/CrudPage";
import { BulkEnrollButton, enrollmentColumns, enrollmentFields, enrollmentFilters } from "@/components/pageDefs";
import { ApiError, samsRequest } from "@/lib/api";
import { alertError, confirmDialog, promptReason, showBatchSummary, toastSuccess } from "@/lib/swal";
import type { Enrollment, EnrollmentBatchResult } from "@/lib/types";

function EnrollmentRowActions({ row, refresh }: { row: Enrollment; refresh: () => void }) {
  const records = row.attendance_record_count ?? 0;
  const who = `${row.student_code} · ${row.course_code}`;

  const withdraw = async () => {
    const reason = await promptReason(`ถอนการลงทะเบียน ${who} — ระบุเหตุผล`);
    if (reason === null) return;
    try {
      const { envelope } = await samsRequest({
        url: `/enrollments/${row.id}/withdraw/`,
        method: "POST",
        data: { reason },
      });
      await toastSuccess(envelope.message || "ถอนการลงทะเบียนสำเร็จ");
      refresh();
    } catch (error) {
      await alertError("ถอนการลงทะเบียนไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    }
  };

  const reinstate = async () => {
    const confirmed = await confirmDialog({
      title: "ยืนยันลงทะเบียนใหม่",
      text: `${who} จะกลับมามีสถานะ "กำลังศึกษา" — ประวัติเช็คชื่อเดิม (ถ้ามี) ยังอยู่`,
      confirmText: "ลงทะเบียนใหม่",
      icon: "question",
    });
    if (!confirmed) return;
    try {
      const { envelope } = await samsRequest({
        url: `/enrollments/${row.id}/reinstate/`,
        method: "POST",
        data: {},
      });
      await toastSuccess(envelope.message || "ลงทะเบียนใหม่สำเร็จ");
      refresh();
    } catch (error) {
      await alertError("ลงทะเบียนใหม่ไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    }
  };

  const remove = async () => {
    if (records > 0) {
      await alertError(
        "ลบการลงทะเบียนไม่ได้",
        `นักศึกษามีประวัติเช็คชื่อ ${records} ครั้งในรายวิชานี้ — ใช้ปุ่ม "ถอน" เพื่อเก็บประวัติแทนการลบ`,
      );
      return;
    }
    const confirmed = await confirmDialog({
      title: "ยืนยันลบการลงทะเบียนถาวร",
      text: `${who} — ใช้เฉพาะกรณีลงทะเบียนผิดพลาดและยังไม่มีประวัติเช็คชื่อ ลบแล้วกู้คืนไม่ได้ (ระบบบันทึก audit ไว้)`,
      confirmText: "ลบถาวร",
    });
    if (!confirmed) return;
    try {
      await samsRequest({ url: `/enrollments/${row.id}/`, method: "DELETE" });
      await toastSuccess("ลบการลงทะเบียนสำเร็จ");
      refresh();
    } catch (error) {
      await alertError("ลบการลงทะเบียนไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    }
  };

  return (
    <>
      {row.enrollment_status === "enrolled" && (
        <button
          type="button"
          onClick={() => void withdraw()}
          className="rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
        >
          ถอน
        </button>
      )}
      {row.enrollment_status === "dropped" && (
        <button
          type="button"
          onClick={() => void reinstate()}
          className="rounded-lg border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100"
        >
          ลงทะเบียนใหม่
        </button>
      )}
      <button
        type="button"
        onClick={() => void remove()}
        title={records > 0 ? "มีประวัติเช็คชื่อ — ใช้ถอนการลงทะเบียนแทน" : "ลบการลงทะเบียนถาวร"}
        className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
      >
        ลบ
      </button>
    </>
  );
}

/** Non-success rows of a batch response, ready for the summary dialog. */
function batchDetails(result: EnrollmentBatchResult): string[] {
  return result.results
    .filter((row) => !row.ok || row.skipped)
    .map((row) => {
      const who = [row.student_code, row.course_code].filter(Boolean).join(" · ") || row.id;
      return `${row.skipped ? "ข้าม" : "ไม่สำเร็จ"}: ${who} — ${row.message}`;
    });
}

/**
 * Batch actions for the selected rows. Each row is processed independently by
 * the backend, so one row that breaks a rule never cancels the whole batch.
 */
function EnrollmentBatchActions({
  rows,
  refresh,
  clearSelection,
}: {
  rows: Enrollment[];
  refresh: () => void;
  clearSelection: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const count = rows.length;
  const withHistory = rows.filter((row) => (row.attendance_record_count ?? 0) > 0).length;
  const completed = rows.filter((row) => row.enrollment_status === "completed").length;
  const alreadyDropped = rows.filter((row) => row.enrollment_status === "dropped").length;

  const applyResult = async (result: EnrollmentBatchResult | undefined, action: string) => {
    if (!result) {
      await alertError(`${action}ไม่สำเร็จ`, "ระบบไม่ได้รับผลลัพธ์จากเซิร์ฟเวอร์");
      return;
    }
    const details = batchDetails(result);
    await showBatchSummary({
      icon: result.failed > 0 ? "warning" : "success",
      title: result.failed > 0 ? `${action}เสร็จบางส่วน` : `${action}สำเร็จ`,
      summary: `สำเร็จ ${result.succeeded} รายการ · ข้าม ${result.skipped} รายการ · ไม่สำเร็จ ${result.failed} รายการ`,
      details,
    });
    // Keep the selection only when nothing changed, so failed rows can be retried.
    if (result.succeeded > 0) clearSelection();
    refresh();
  };

  const withdrawSelected = async () => {
    const notes: string[] = [];
    if (completed > 0) notes.push(`${completed} รายการที่จบรายวิชาแล้วจะไม่ถูกถอน`);
    if (alreadyDropped > 0) notes.push(`${alreadyDropped} รายการที่ถอนอยู่แล้วจะถูกข้าม`);
    const reason = await promptReason(
      `ถอนการลงทะเบียน ${count} รายการ — ระบุเหตุผล`,
      `${notes.length > 0 ? `${notes.join(" · ")}. ` : ""}ประวัติเช็คชื่อของรายการที่ถอนสำเร็จจะยังอยู่ครบ`,
    );
    if (reason === null) return;
    setBusy(true);
    try {
      const { data } = await samsRequest<EnrollmentBatchResult>({
        url: "/enrollments/batch-withdraw/",
        method: "POST",
        data: { ids: rows.map((row) => row.id), reason },
      });
      await applyResult(data, "ถอนการลงทะเบียน");
    } catch (error) {
      await alertError(
        "ถอนการลงทะเบียนไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  const deleteSelected = async () => {
    if (withHistory === count) {
      await alertError(
        "ลบการลงทะเบียนไม่ได้",
        `ทั้ง ${count} รายการมีประวัติเช็คชื่อ — ใช้ปุ่ม "ถอนที่เลือก" เพื่อเก็บประวัติแทนการลบ`,
      );
      return;
    }
    const confirmed = await confirmDialog({
      title: `ยืนยันลบการลงทะเบียน ${count} รายการ`,
      text:
        withHistory > 0
          ? `มี ${withHistory} รายการที่มีประวัติเช็คชื่อและจะไม่ถูกลบ (ใช้ "ถอน" แทน) — อีก ${count - withHistory} รายการจะถูกลบถาวรและกู้คืนไม่ได้ (ระบบบันทึก audit ไว้)`
          : "ทุกรายการยังไม่มีประวัติเช็คชื่อ จะถูกลบถาวรและกู้คืนไม่ได้ (ระบบบันทึก audit ไว้)",
      confirmText: "ลบถาวร",
    });
    if (!confirmed) return;
    setBusy(true);
    try {
      const { data } = await samsRequest<EnrollmentBatchResult>({
        url: "/enrollments/batch-delete/",
        method: "POST",
        data: { ids: rows.map((row) => row.id) },
      });
      await applyResult(data, "ลบการลงทะเบียน");
    } catch (error) {
      await alertError(
        "ลบการลงทะเบียนไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        type="button"
        onClick={() => void withdrawSelected()}
        disabled={busy}
        className="rounded-lg border border-amber-300 bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        ถอนที่เลือก ({count})
      </button>
      <button
        type="button"
        onClick={() => void deleteSelected()}
        disabled={busy}
        className="rounded-lg border border-red-300 bg-red-100 px-3 py-1.5 text-xs font-medium text-red-700 hover:bg-red-200 disabled:cursor-not-allowed disabled:opacity-50"
      >
        ลบที่เลือก ({count})
      </button>
      {busy && <span className="text-xs text-blue-700">กำลังดำเนินการ…</span>}
    </>
  );
}

export default function EnrollmentPanel({
  createTitle = "เพิ่มการลงทะเบียน",
  searchPlaceholder = "ค้นหาด้วยรหัสนักศึกษา/ชื่อ…",
}: {
  createTitle?: string;
  searchPlaceholder?: string;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">
        <p className="font-semibold">การแก้ไขการลงทะเบียน</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5">
          <li>
            <strong>ถอนการลงทะเบียน</strong> — ใช้เมื่อรายวิชาเริ่มสอนแล้วหรือมีประวัติเช็คชื่อ: สถานะจะเป็น
            &quot;ถอนรายวิชา&quot; และประวัติยังอยู่ครบ (ลงทะเบียนใหม่ได้ถ้ารายวิชายังไม่จบ)
          </li>
          <li>
            <strong>ลบการลงทะเบียน</strong> — ใช้เฉพาะกรณีลงผิดและยังไม่มีประวัติเช็คชื่อเท่านั้น
            ถ้ามีประวัติระบบจะไม่ยอมให้ลบ
          </li>
          <li>ระบบไม่อนุญาตให้เพิ่มการลงทะเบียนในรายวิชาที่จบภาคเรียนหรือถูกยกเลิกแล้ว</li>
          <li>
            <strong>เลือกหลายรายการ</strong> — ติ๊กช่องหน้าตารางแล้วใช้ &quot;ถอนที่เลือก&quot; หรือ &quot;ลบที่เลือก&quot;:
            ระบบทำทีละรายการและสรุปผลรายแถว (ครั้งละไม่เกิน 200 รายการ)
          </li>
        </ul>
      </div>
      <CrudPage<Enrollment>
        title="การลงทะเบียน"
        basePath="/enrollments/"
        fields={enrollmentFields}
        createTitle={createTitle}
        searchPlaceholder={searchPlaceholder}
        emptyMessage="ยังไม่มีรายการลงทะเบียน"
        columns={enrollmentColumns}
        filters={enrollmentFilters}
        canDelete={false}
        selectable
        selectionActions={(rows, refresh, clearSelection) => (
          <EnrollmentBatchActions rows={rows} refresh={refresh} clearSelection={clearSelection} />
        )}
        rowActions={(row, refresh) => <EnrollmentRowActions row={row} refresh={refresh} />}
        headerExtra={(refresh) => <BulkEnrollButton refresh={refresh} />}
      />
    </div>
  );
}
