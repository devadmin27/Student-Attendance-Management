"use client";
/**
 * Printable A4 leave document (Phase 3).
 *
 * One route serves all three roles; the backend scopes the payload:
 * students/admins get every affected course, while an instructor's copy
 * contains only the offerings they teach. The page is intentionally outside
 * AppShell so browser print output contains only the document.
 *
 * Phase 2 (request-level approvals) can be added as a conditional section
 * under "ความเห็นอาจารย์รายวิชา" without changing this page's data flow.
 */
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useRequireRole, type Role } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiDateTime } from "@/lib/format";
import type { LeavePrintCourse, LeavePrintDocument } from "@/lib/types";

const ALLOWED_ROLES: Role[] = ["student", "instructor", "admin"];

const PRINT_STYLES = `
@page { size: A4; margin: 12mm; }
@media print {
  html, body { background: #fff !important; }
  .leave-print-toolbar { display: none !important; }
  .leave-print-shell { background: #fff !important; padding: 0 !important; }
  .leave-print-sheet {
    box-shadow: none !important;
    margin: 0 !important;
    width: auto !important;
    max-width: none !important;
    min-height: 0 !important;
    border: 0 !important;
    padding: 0 !important;
  }
  .leave-print-avoid-break {
    break-inside: avoid;
    page-break-inside: avoid;
  }
}
`;

const DOCUMENT_FONT =
  '"TH Sarabun New", "Sarabun", "Noto Sans Thai", "Leelawadee UI", Arial, sans-serif';

function timeRange(start: string | null, end: string | null): string {
  if (!start || !end) return "ลาทั้งวัน";
  return `${start.slice(0, 5)}–${end.slice(0, 5)}`;
}

function scheduleText(course: LeavePrintCourse): string {
  if (course.schedules.length === 0) return "ยังไม่มีตารางเรียน";
  return course.schedules
    .map(
      (schedule) =>
        `วัน${schedule.weekday_display} ${schedule.start_time}–${schedule.end_time}${
          schedule.classroom ? ` (${schedule.classroom})` : ""
        }`,
    )
    .join(" · ");
}

const cellClass = "border border-slate-400 px-2 py-1.5 align-top text-left";
const headCellClass =
  "border border-slate-400 px-2 py-1.5 align-top text-left font-semibold";

export default function LeavePrintPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
          กำลังโหลดเอกสาร…
        </div>
      }
    >
      <LeavePrintContent />
    </Suspense>
  );
}

function LeavePrintContent() {
  const user = useRequireRole(ALLOWED_ROLES);
  const params = useParams<{ id: string }>();
  const requestId = params.id;
  const [document, setDocument] = useState<LeavePrintDocument | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<LeavePrintDocument>({
          url: `/leave-requests/${requestId}/print/`,
        });
        if (!cancelled) setDocument(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError ? err.message : "โหลดเอกสารใบลาไม่สำเร็จ",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  const backHref =
    user?.role === "student"
      ? `/student/leaves/${requestId}`
      : user?.role === "admin"
        ? `/admin/leaves/${requestId}`
        : "/instructor/leaves";

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-slate-500">
        กำลังโหลดเอกสาร…
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-sm text-red-600">{error ?? "ไม่พบเอกสารใบลา"}</p>
        <Link href={backHref} className="text-sm text-blue-700 hover:underline">
          ← กลับ
        </Link>
      </div>
    );
  }

  const isDraft = document.status === "draft";
  const isCancelled = document.status === "cancelled";
  const coursesWithReviews = document.courses.filter(
    (course) => course.reviews.length > 0,
  );

  return (
    <div className="leave-print-shell min-h-screen bg-slate-100 py-6">
      <style>{PRINT_STYLES}</style>

      <div className="leave-print-toolbar mx-auto mb-4 flex w-full max-w-[210mm] flex-wrap items-center justify-between gap-3 px-4">
        <Link href={backHref} className="text-sm text-blue-700 hover:underline">
          ← กลับ
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          พิมพ์เอกสาร (A4)
        </button>
      </div>

      <article
        className="leave-print-sheet mx-auto w-full max-w-[210mm] bg-white p-[14mm] text-slate-900 shadow-lg"
        style={{ fontFamily: DOCUMENT_FONT }}
      >
        <header className="flex items-start justify-between gap-4 border-b-2 border-slate-800 pb-3">
          <div>
            <div className="text-xl font-bold tracking-wide">SAMS</div>
            <div className="text-xs text-slate-600">
              วิทยาลัยการสาธารณสุขสิรินธร จังหวัดตรัง
            </div>
          </div>
          <div className="text-right">
            <h1 className="text-2xl font-bold">ใบลาป่วย / ลากิจส่วนตัว</h1>
            <div className="mt-1 text-xs text-slate-600">
              รหัสอ้างอิง: {document.id.slice(0, 8).toUpperCase()}
            </div>
          </div>
        </header>

        {(isDraft || isCancelled) && (
          <div className="mt-3 inline-block border border-slate-500 px-3 py-1 text-xs font-semibold">
            {isDraft ? "แบบร่าง — ยังไม่ส่งคำร้อง" : "คำร้องนี้ถูกยกเลิกแล้ว"}
          </div>
        )}

        <div className="mt-3 space-y-0.5 text-sm">
          <p>
            <span className="inline-block w-14 font-semibold">เรื่อง</span>
            ขอลาป่วย / ลากิจส่วนตัว
          </p>
          <p>
            <span className="inline-block w-14 font-semibold">เรียน</span>
            ผู้อำนวยการวิทยาลัยการสาธารณสุขสิรินธร จังหวัดตรัง
          </p>
        </div>

        <table className="mt-3 w-full border-collapse text-sm">
          <tbody>
            <tr>
              <th className={`${headCellClass} w-32`}>ชื่อ-นามสกุล</th>
              <td className={cellClass}>{document.student_name}</td>
              <th className={`${headCellClass} w-28`}>รหัสนักศึกษา</th>
              <td className={`${cellClass} w-32`}>{document.student_code}</td>
            </tr>
            <tr>
              <th className={headCellClass}>หลักสูตร</th>
              <td className={cellClass} colSpan={3}>
                {document.student_program_name ?? "-"}
                {document.student_class_group_name
                  ? ` · ${document.student_class_group_name}`
                  : ""}{" "}
                · ชั้นปี {document.student_year_level}
              </td>
            </tr>
            <tr>
              <th className={headCellClass}>ประเภทการลา</th>
              <td className={cellClass}>{document.leave_type_display}</td>
              <th className={headCellClass}>สถานะคำร้อง</th>
              <td className={cellClass}>{document.status_display}</td>
            </tr>
            <tr>
              <th className={headCellClass}>ช่วงที่ลา</th>
              <td className={cellClass}>
                {formatThaiDate(document.start_date)} —{" "}
                {formatThaiDate(document.end_date)}
                <div className="text-slate-600">
                  มีกำหนดเวลา {document.total_days} วัน
                </div>
              </td>
              <th className={headCellClass}>เวลา</th>
              <td className={cellClass}>
                {timeRange(document.start_time, document.end_time)}
              </td>
            </tr>
            <tr>
              <th className={headCellClass}>โทรศัพท์</th>
              <td className={cellClass}>{document.contact_phone || "-"}</td>
              <th className={headCellClass}>LINE ID</th>
              <td className={cellClass}>{document.line_id || "-"}</td>
            </tr>
            <tr>
              <th className={headCellClass}>ที่อยู่ระหว่างการลา</th>
              <td className={cellClass} colSpan={3}>
                {document.address_during_leave || "-"}
              </td>
            </tr>
            <tr>
              <th className={headCellClass}>ส่งคำร้องเมื่อ</th>
              <td className={cellClass}>
                {document.submitted_at
                  ? formatThaiDateTime(document.submitted_at)
                  : "-"}
              </td>
              <th className={headCellClass}>พิมพ์เมื่อ</th>
              <td className={cellClass}>
                {formatThaiDateTime(document.generated_at)}
              </td>
            </tr>
          </tbody>
        </table>

        <section className="mt-4">
          <h2 className="text-sm font-bold">เหตุผลการลา</h2>
          <p className="mt-1 min-h-[56px] whitespace-pre-wrap border border-slate-400 px-3 py-2 text-sm">
            {document.reason}
          </p>
        </section>

        <section className="mt-4">
          <h2 className="text-sm font-bold">ผู้ปกครอง</h2>
          <table className="mt-1 w-full border-collapse text-sm">
            <tbody>
              <tr>
                <th className={`${headCellClass} w-32`}>รับทราบการลา</th>
                <td className={cellClass}>
                  {document.guardian_acknowledged
                    ? "ผู้ปกครองรับทราบแล้ว"
                    : "ยังไม่ยืนยัน"}
                </td>
                <th className={`${headCellClass} w-28`}>โทรศัพท์</th>
                <td className={cellClass}>{document.guardian_phone || "-"}</td>
              </tr>
              <tr>
                <th className={headCellClass}>ที่อยู่</th>
                <td className={cellClass} colSpan={3}>
                  {document.guardian_address || "-"}
                </td>
              </tr>
            </tbody>
          </table>
        </section>

        <section className="mt-5">
          <h2 className="text-sm font-bold">
            รายวิชาที่ได้รับผลกระทบ ({document.courses.length})
          </h2>
          {document.scope === "course" && (
            <p className="mt-1 text-xs text-slate-600">
              เอกสารฉบับนี้แสดงเฉพาะรายวิชาที่คุณเป็นผู้สอน
            </p>
          )}
          <table className="mt-2 w-full border-collapse text-xs">
            <thead>
              <tr>
                <th className={headCellClass}>รายวิชา</th>
                <th className={headCellClass}>ภาค / กลุ่ม</th>
                <th className={headCellClass}>ตารางเรียน</th>
                <th className={headCellClass}>ช่วงที่กระทบ</th>
                <th className={headCellClass}>ผลการพิจารณา</th>
              </tr>
            </thead>
            <tbody>
              {document.courses.map((course) => (
                <tr key={course.id} className="leave-print-avoid-break">
                  <td className={cellClass}>
                    <div className="font-semibold">{course.course_code}</div>
                    <div>{course.course_name}</div>
                    {course.instructor_names.length > 0 && (
                      <div className="mt-0.5 text-slate-600">
                        ผู้สอน: {course.instructor_names.join(", ")}
                      </div>
                    )}
                  </td>
                  <td className={cellClass}>
                    {course.term_label}
                    {course.class_group_name
                      ? ` · ${course.class_group_name}`
                      : ""}
                  </td>
                  <td className={cellClass}>{scheduleText(course)}</td>
                  <td className={cellClass}>
                    {formatThaiDate(course.affected_start_date)} —{" "}
                    {formatThaiDate(course.affected_end_date)}
                    <div className="text-slate-600">
                      {timeRange(
                        course.affected_start_time,
                        course.affected_end_time,
                      )}
                    </div>
                  </td>
                  <td className={cellClass}>
                    {course.review_status_display}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {coursesWithReviews.length > 0 && (
          <section className="mt-5">
            <h2 className="text-sm font-bold">ความเห็นอาจารย์รายวิชา</h2>
            <div className="mt-2 space-y-3">
              {coursesWithReviews.map((course) => (
                <div
                  key={course.id}
                  className="leave-print-avoid-break border border-slate-400 px-3 py-2 text-xs"
                >
                  <div className="font-semibold">
                    {course.course_code} — {course.course_name}
                  </div>
                  <div className="mt-1 space-y-1.5">
                    {course.reviews.map((review) => (
                      <div key={review.id}>
                        <div className="flex flex-wrap gap-x-3">
                          <span className="font-medium">
                            {review.reviewer_name}
                          </span>
                          <span>{review.review_status_display}</span>
                          <span className="text-slate-600">
                            {formatThaiDateTime(review.created_at)}
                          </span>
                        </div>
                        {review.comment && (
                          <p className="mt-0.5 whitespace-pre-wrap">
                            {review.comment}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

        <section className="leave-print-avoid-break mt-10 flex justify-end">
          <div className="w-72 text-center text-xs">
            <p>ลงชื่อ ...........................................................</p>
            <p className="mt-10">({document.student_name})</p>
            <p>ผู้ยื่นคำร้อง</p>
            <p className="mt-2">
              วันที่ ........... / ........... / ...........
            </p>
          </div>
        </section>

        <footer className="mt-8 border-t border-slate-300 pt-2 text-[10px] text-slate-500">
          เอกสารนี้สร้างจากระบบ SAMS เมื่อ{" "}
          {formatThaiDateTime(document.generated_at)} · สถานะการเข้าเรียนแยกจาก
          สถานะใบลาและไม่ถูกเปลี่ยนโดยอัตโนมัติ
        </footer>
      </article>
    </div>
  );
}
