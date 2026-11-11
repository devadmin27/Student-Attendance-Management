"use client";
/** Shared student leave form: create a draft / edit a draft / save & submit. */
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate } from "@/lib/format";
import { alertError, toastSuccess } from "@/lib/swal";
import type {
  AvailableLeaveCourse,
  LeaveRequest,
  LeaveType,
} from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const LEAVE_TYPES: { value: LeaveType; label: string }[] = [
  { value: "sick", label: "ลาป่วย" },
  { value: "personal", label: "ลากิจส่วนตัว" },
  { value: "other", label: "ลาอื่น ๆ" },
];

function affectedSummary(course: AvailableLeaveCourse): string {
  if (course.affected_count === 0) return "ไม่พบคาบเรียนตรงกับช่วงที่ลา";
  const dates = course.affected_dates.slice(0, 3).map(formatThaiDate);
  const more =
    course.affected_dates.length > dates.length
      ? ` และอีก ${course.affected_dates.length - dates.length} วัน`
      : "";
  return `กระทบ ${course.affected_count} คาบ: ${dates.join(", ")}${more}`;
}

export default function LeaveForm({ requestId }: { requestId?: string }) {
  const router = useRouter();
  const isEdit = Boolean(requestId);

  const [leaveType, setLeaveType] = useState<LeaveType>("personal");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [startTime, setStartTime] = useState("");
  const [endTime, setEndTime] = useState("");
  const [reason, setReason] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [available, setAvailable] = useState<AvailableLeaveCourse[]>([]);
  const [availableLoading, setAvailableLoading] = useState(false);
  const [availableError, setAvailableError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(isEdit);
  const [saving, setSaving] = useState<"draft" | "submit" | null>(null);

  // Edit mode: load the draft and preselect its current courses.
  useEffect(() => {
    if (!requestId) return;
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<LeaveRequest>({
          url: `/leave-requests/${requestId}/`,
        });
        if (cancelled) return;
        if (!data.is_editable) {
          await alertError("คำร้องนี้แก้ไขไม่ได้", "แก้ไขได้เฉพาะคำร้องที่เป็นแบบร่าง");
          router.replace(`/student/leaves/${requestId}`);
          return;
        }
        setLeaveType(data.leave_type);
        setStartDate(data.start_date);
        setEndDate(data.end_date);
        setStartTime(data.start_time?.slice(0, 5) ?? "");
        setEndTime(data.end_time?.slice(0, 5) ?? "");
        setReason(data.reason);
        setSelected(new Set(data.courses.map((course) => course.course_offering)));
      } catch (error) {
        if (!cancelled) {
          await alertError(
            "โหลดคำร้องไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
      } finally {
        if (!cancelled) setInitialLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [requestId, router]);

  // Suggest affected courses whenever the leave window changes.
  useEffect(() => {
    let cancelled = false;
    const timer = setTimeout(() => {
      void (async () => {
        if (!startDate || !endDate || endDate < startDate) {
          if (!cancelled) {
            setAvailable([]);
            setAvailableError(null);
          }
          return;
        }
        if ((startTime && !endTime) || (!startTime && endTime)) {
          if (!cancelled) {
            setAvailable([]);
            setAvailableError(
              "กรุณาระบุเวลาเริ่มและเวลาสิ้นสุดพร้อมกัน หรือเว้นทั้งคู่",
            );
          }
          return;
        }
        setAvailableLoading(true);
        setAvailableError(null);
        try {
          const params: Record<string, string> = {
            start_date: startDate,
            end_date: endDate,
          };
          if (startTime && endTime) {
            params.start_time = startTime;
            params.end_time = endTime;
          }
          const { data } = await samsRequest<AvailableLeaveCourse[]>({
            url: "/leave-requests/available-courses/",
            params,
          });
          if (!cancelled) setAvailable(data ?? []);
        } catch (error) {
          if (!cancelled) {
            setAvailable([]);
            setAvailableError(
              error instanceof ApiError
                ? error.message
                : "โหลดรายวิชาที่เกี่ยวข้องไม่สำเร็จ",
            );
          }
        } finally {
          if (!cancelled) setAvailableLoading(false);
        }
      })();
    }, 350);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [startDate, endDate, startTime, endTime]);

  const selectedCourses = useMemo(
    () => available.filter((course) => selected.has(course.id)),
    [available, selected],
  );

  const toggleCourse = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const validate = (needCourses: boolean): string | null => {
    if (!startDate || !endDate) return "กรุณาระบุวันที่เริ่มลาและวันที่สิ้นสุดการลา";
    if (endDate < startDate) return "วันที่สิ้นสุดการลาต้องไม่ก่อนวันที่เริ่มลา";
    if ((startTime && !endTime) || (!startTime && endTime)) {
      return "กรุณาระบุเวลาเริ่มและเวลาสิ้นสุดพร้อมกัน หรือเว้นทั้งคู่";
    }
    if (startTime && endTime) {
      if (startDate === endDate && endTime <= startTime) {
        return "เวลาสิ้นสุดการลาต้องอยู่หลังเวลาเริ่มลา";
      }
    }
    if (!reason.trim()) return "กรุณาระบุเหตุผลการลา";
    if (needCourses && selected.size === 0) return "กรุณาเลือกอย่างน้อย 1 รายวิชา";
    return null;
  };

  const save = async (submitAfter: boolean) => {
    const problem = validate(submitAfter);
    if (problem) {
      await alertError("ข้อมูลยังไม่ครบถ้วน", problem);
      return;
    }
    setSaving(submitAfter ? "submit" : "draft");
    const payload = {
      leave_type: leaveType,
      start_date: startDate,
      end_date: endDate,
      start_time: startTime || null,
      end_time: endTime || null,
      reason: reason.trim(),
      course_offering_ids: Array.from(selected),
    };
    try {
      const result = requestId
        ? await samsRequest<LeaveRequest>({
            url: `/leave-requests/${requestId}/`,
            method: "PATCH",
            data: payload,
          })
        : await samsRequest<LeaveRequest>({
            url: "/leave-requests/",
            method: "POST",
            data: payload,
          });
      let latest = result.data;
      if (submitAfter) {
        const submitted = await samsRequest<LeaveRequest>({
          url: `/leave-requests/${latest.id}/submit/`,
          method: "POST",
          data: {},
        });
        latest = submitted.data;
        await toastSuccess(submitted.envelope.message);
      } else {
        await toastSuccess(result.envelope.message);
      }
      router.push(`/student/leaves/${latest.id}`);
    } catch (error) {
      await alertError(
        "บันทึกคำร้องไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setSaving(null);
    }
  };

  if (initialLoading) {
    return <p className="animate-pulse text-slate-500">กำลังโหลดคำร้อง…</p>;
  }

  return (
    <div className="space-y-5">
      <div className="text-sm text-slate-600">
        <Link href="/student/leaves" className="text-blue-700 hover:underline">
          ← กลับรายการใบลา
        </Link>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
        <h2 className="text-sm font-semibold text-slate-800">รายละเอียดการลา</h2>
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <label htmlFor="leave-type" className="mb-1 block text-xs font-medium text-slate-500">
              ประเภทการลา *
            </label>
            <select
              id="leave-type"
              value={leaveType}
              onChange={(e) => setLeaveType(e.target.value as LeaveType)}
              className={inputClass}
            >
              {LEAVE_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div />
          <div>
            <label htmlFor="start-date" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่เริ่มลา *
            </label>
            <input
              id="start-date"
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="end-date" className="mb-1 block text-xs font-medium text-slate-500">
              วันที่สิ้นสุดการลา *
            </label>
            <input
              id="end-date"
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="start-time" className="mb-1 block text-xs font-medium text-slate-500">
              เวลาเริ่มลา (ไม่บังคับ)
            </label>
            <input
              id="start-time"
              type="time"
              value={startTime}
              onChange={(e) => setStartTime(e.target.value)}
              className={inputClass}
            />
          </div>
          <div>
            <label htmlFor="end-time" className="mb-1 block text-xs font-medium text-slate-500">
              เวลาสิ้นสุดการลา (ไม่บังคับ)
            </label>
            <input
              id="end-time"
              type="time"
              value={endTime}
              onChange={(e) => setEndTime(e.target.value)}
              className={inputClass}
            />
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-500">
          ไม่ระบุเวลา = ลาทั้งวัน · หากระบุเวลาต้องระบุทั้งเวลาเริ่มและเวลาสิ้นสุด
        </p>
        <div className="mt-4">
          <label htmlFor="reason" className="mb-1 block text-xs font-medium text-slate-500">
            เหตุผลการลา *
          </label>
          <textarea
            id="reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={4}
            placeholder="ระบุเหตุผลและข้อมูลประกอบการลา"
            className={inputClass}
          />
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm md:p-5">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-sm font-semibold text-slate-800">รายวิชาที่ได้รับผลกระทบ</h2>
          <span className="text-xs text-slate-500">
            เลือกได้หลายรายวิชา ไม่จำกัดจำนวน · เลือกแล้ว {selected.size} รายวิชา
          </span>
        </div>
        <p className="mt-1 text-xs text-slate-500">
          รายการด้านล่างมาจากการลงทะเบียนและตารางเรียนจริง — รายวิชาที่ไม่พบคาบตรงกับช่วงลาก็เลือกได้
        </p>

        {availableError && (
          <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {availableError}
          </p>
        )}
        {availableLoading ? (
          <p className="mt-4 animate-pulse text-sm text-slate-500">กำลังตรวจสอบตารางเรียน…</p>
        ) : !startDate || !endDate ? (
          <p className="mt-4 text-sm text-slate-500">กรุณาระบุช่วงวันที่ลาเพื่อแสดงรายวิชา</p>
        ) : available.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">ไม่พบรายวิชาที่ลงทะเบียนในภาคการศึกษานี้</p>
        ) : (
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {available.map((course) => {
              const checked = selected.has(course.id);
              return (
                <label
                  key={course.id}
                  className={`flex cursor-pointer gap-3 rounded-xl border p-3 transition ${
                    checked
                      ? "border-blue-400 bg-blue-50/60"
                      : "border-slate-200 bg-white hover:border-blue-200"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleCourse(course.id)}
                    className="mt-1 h-4 w-4 shrink-0 accent-blue-700"
                  />
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-slate-900">
                      {course.course_code} — {course.course_name}
                    </div>
                    <div className="mt-0.5 text-xs text-slate-500">
                      ภาค {course.term_label}
                      {course.class_group_name ? ` · ${course.class_group_name}` : ""}
                    </div>
                    <div className="mt-1 text-xs text-slate-600">
                      {course.schedules.length > 0
                        ? course.schedules
                            .map(
                              (s) =>
                                `วัน${s.weekday_display} ${s.start_time}–${s.end_time}${
                                  s.classroom ? ` (${s.classroom})` : ""
                                }`,
                            )
                            .join(" · ")
                        : "ยังไม่มีตารางเรียน"}
                    </div>
                    <div
                      className={`mt-1 text-xs ${
                        course.has_class_in_period ? "text-emerald-700" : "text-amber-700"
                      }`}
                    >
                      {affectedSummary(course)}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        )}

        {selectedCourses.length > 0 && (
          <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="text-xs font-medium text-slate-600">รายการที่เลือก</div>
            <div className="mt-1 flex flex-wrap gap-1.5">
              {selectedCourses.map((course) => (
                <span
                  key={course.id}
                  className="rounded-full bg-white px-2 py-0.5 text-xs text-slate-700 ring-1 ring-slate-200"
                >
                  {course.course_code}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap justify-end gap-2">
        <Link
          href={requestId ? `/student/leaves/${requestId}` : "/student/leaves"}
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          ยกเลิก
        </Link>
        <button
          type="button"
          onClick={() => void save(false)}
          disabled={saving !== null}
          className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100 disabled:opacity-50"
        >
          {saving === "draft" ? "กำลังบันทึก…" : isEdit ? "บันทึกการแก้ไข" : "บันทึกร่าง"}
        </button>
        <button
          type="button"
          onClick={() => void save(true)}
          disabled={saving !== null}
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
        >
          {saving === "submit" ? "กำลังส่งคำร้อง…" : "บันทึกและส่งคำร้อง"}
        </button>
      </div>
    </div>
  );
}
