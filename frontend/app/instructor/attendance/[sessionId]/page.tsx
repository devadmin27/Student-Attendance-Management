"use client";
/**
 * Instructor attendance control room.
 * - Session lifecycle (open → pause → close / cancel)
 * - Rotating QR token displayed on-screen; re-issues automatically before expiry
 * - Live roster (polls every few seconds) + audited manual status edit
 */
import Link from "next/link";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import QRCode from "react-qr-code";
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiTime } from "@/lib/format";
import { alertError, confirmDialog, promptReason, toastSuccess } from "@/lib/swal";
import type { AttendanceRecord, AttendanceSession, QRTokenInfo, RosterRow } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

export default function SessionControlPage() {
  return (
    <Suspense fallback={<div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>}>
      <SessionControlContent />
    </Suspense>
  );
}

function SessionControlContent() {
  const user = useRequireRole(["instructor"]);
  const params = useParams<{ sessionId: string }>();
  const sessionId = params.sessionId;

  const [session, setSession] = useState<AttendanceSession | null>(null);
  const [roster, setRoster] = useState<RosterRow[]>([]);
  const [records, setRecords] = useState<AttendanceRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<QRTokenInfo | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [actionBusy, setActionBusy] = useState(false);
  const [rosterAutoRefresh, setRosterAutoRefresh] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const ONE_SHOT_REISSUE_MARGIN = 2; // seconds before expiry

  const loadSession = useCallback(async () => {
    try {
      const { data } = await samsRequest<AttendanceSession>({
        url: `/attendance/sessions/${sessionId}/`,
      });
      setSession(data);
      return data;
    } catch (error) {
      await alertError(
        "โหลดคาบเรียนไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
      return null;
    }
  }, [sessionId]);

  const loadRoster = useCallback(async () => {
    try {
      const [rosterRes, recordRes] = await Promise.all([
        samsRequest<RosterRow[]>({ url: `/attendance/sessions/${sessionId}/roster/` }),
        samsRequest<AttendanceRecord[]>({
          url: "/attendance/records/",
          params: { attendance_session: sessionId, page_size: 100 },
        }),
      ]);
      setRoster(rosterRes.data ?? []);
      setRecords(recordRes.data ?? []);
    } catch (error) {
      await alertError(
        "โหลดรายชื่อคาบไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    }
  }, [sessionId]);

  const issueQrToken = useCallback(
    async (silent = false) => {
      try {
        const { data, envelope } = await samsRequest<QRTokenInfo>({
          url: `/attendance/sessions/${sessionId}/qr-token/`,
          method: "POST",
          data: {},
        });
        setToken(data);
        const remaining = Math.max(1, Number(data.expires_in_seconds ?? 30));
        setSecondsLeft(remaining);
        if (!silent) {
          void toastSuccess(envelope.message ?? "ออก QR Code สำเร็จ");
        }
        return data;
      } catch (error) {
        if (!silent) {
          await alertError(
            "ออก QR Code ไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
        return null;
      }
    },
    [sessionId],
  );

  useEffect(() => {
    void (async () => {
      const s = await loadSession();
      await loadRoster();
      if (s && s.status === "open") {
        await issueQrToken(true);
      }
      setLoading(false);
    })();
  }, [loadSession, loadRoster, issueQrToken]);

  // Roster live refresh
  useEffect(() => {
    if (!rosterAutoRefresh) return;
    const interval = setInterval(() => {
      void loadRoster();
    }, 5000);
    return () => clearInterval(interval);
  }, [rosterAutoRefresh, loadRoster]);

  // QR token countdown + auto re-issue shortly before expiry
  useEffect(() => {
    if (!token || !session || session.status !== "open") return;
    const interval = setInterval(() => {
      setSecondsLeft((prev) => {
        const next = Math.max(0, prev - 1);
        if (next <= ONE_SHOT_REISSUE_MARGIN) {
          // Rotate immediately: each new token invalidates the previous one.
          void issueQrToken(true);
          return next;
        }
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, session]);

  const lifecycle = async (action: "open" | "pause" | "close" | "cancel") => {
    const texts: Record<string, string> = {
      open: "เปิดเช็คชื่อและแสดง QR Code ให้นักศึกษาสแกน",
      pause: "หยุดคาบชั่วคราว (QR ที่แสดงจะใช้ไม่ได้ทันที)",
      close: "ปิดคาบและบันทึกขาดเรียนผู้ที่ไม่ได้เช็คชื่อทั้งหมด",
      cancel: "ยกเลิกคาบเรียน (ไม่สามารถเช็คชื่อได้อีก)",
    };
    const confirmed = await confirmDialog({
      title: `ยืนยันการ${action === "close" ? "ปิดคาบ" : action === "open" ? "เปิดคาบ" : action === "pause" ? "หยุดคาบชั่วคราว" : "ยกเลิกคาบ"}`,
      text: texts[action],
      confirmText: "ยืนยัน",
    });
    if (!confirmed) return;
    setActionBusy(true);
    try {
      const { data, envelope } = await samsRequest<AttendanceSession>({
        url: `/attendance/sessions/${sessionId}/${action}/`,
        method: "POST",
        data: {},
      });
      setSession(data);
      await toastSuccess(envelope.message);
      if (action === "open") {
        await issueQrToken(true);
      } else {
        setToken(null);
      }
      await loadRoster();
    } catch (error) {
      await alertError(
        "จัดการคาบไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setActionBusy(false);
    }
  };

  const recordByStudent = useMemo(() => {
    const map = new Map<string, AttendanceRecord>();
    for (const r of records) map.set(r.student, r);
    return map;
  }, [records]);

  const editStatus = async (row: RosterRow, nextStatus: string) => {
    const record = recordByStudent.get(row.id);
    if (!record) {
      await alertError(
        "นักศึกษายังไม่มีรายการเช็คชื่อในคาบนี้ เช็คชื่อ (หรือรอปิดคาบสร้างรายการขาดเรียน) ก่อนจึงจะแก้ไขสถานะได้",
      );
      return;
    }
    const reason = await promptReason("เหตุผลการแก้ไขสถานะ (บันทึกลง Audit Log)");
    if (!reason) return;
    try {
      await samsRequest({
        url: `/attendance/records/${record.id}/`,
        method: "PATCH",
        data: { status: nextStatus, edit_reason: reason },
      });
      await toastSuccess("แก้ไขสถานะสำเร็จ (บันทึก Audit แล้ว)");
      await loadRoster();
    } catch (error) {
      await alertError(
        "แก้ไขสถานะไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    }
  };

  const filteredRoster = useMemo(() => {
    if (!statusFilter) return roster;
    if (statusFilter === "not_checked_in") return roster.filter((r) => r.checked_in_status === null);
    return roster.filter((r) => r.checked_in_status === statusFilter);
  }, [roster, statusFilter]);

  if (loading || !session) {
    return (
      <AppShell title="ควบคุมคาบเช็คชื่อ">
        <p className="animate-pulse text-slate-500">กำลังโหลดคาบเรียน…</p>
      </AppShell>
    );
  }

  return (
    <AppShell title={`ควบคุมคาบ — ${session.course_code} ${session.course_name}`}>
      {!user && null}
      <div className="space-y-5">
        <div className="flex items-center gap-3 text-sm text-slate-600">
          <Link href="/instructor/attendance" className="text-blue-700 hover:underline">
            ← กลับรายการคาบเรียน
          </Link>
          <span>·</span>
          <span>วันเรียน {formatThaiDate(session.session_date)}</span>
          <span>·</span>
          <span>
            ช่วงเช็คชื่อ {formatThaiTime(session.check_in_start)} — {formatThaiTime(session.check_in_end)}
          </span>
          <span className="ml-auto">
            <StatusBadge status={session.status} display={session.status_display} />
          </span>
        </div>

        <div className="grid gap-4 lg:grid-cols-5">
          {/* QR display */}
          <div className="lg:col-span-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-sm font-semibold text-slate-800">QR Code เช็คชื่อ (Rotating Token)</h2>
              <p className="mb-3 text-xs text-slate-500">
                Token หมุนเวียนอัตโนมัติก่อนหมดอายุ — ระบบเก็บเฉพาะ SHA-256 hash ไม่เก็บ plaintext
              </p>
              {session.status === "open" ? (
                <div className="space-y-3">
                  <div className="flex justify-center rounded-xl bg-slate-50 p-4">
                    {token ? (
                      <div className="flex flex-col items-center gap-2">
                        <div className="rounded-lg bg-white p-3 shadow-sm">
                          <QRCode value={token.qr} size={190} />
                        </div>
                        <div className="text-xs text-slate-500">
                          หมดอายุในอีก <strong className="tabular-nums text-slate-800">{secondsLeft}s</strong> · ระบบจะหมุนเวียน token ใหม่เอง
                        </div>
                      </div>
                    ) : (
                      <div className="flex h-[220px] w-[220px] items-center justify-center rounded bg-slate-200 animate-pulse text-sm text-slate-500">
                        กำลังออก token…
                      </div>
                    )}
                  </div>
                  <button
                    type="button"
                    onClick={() => void issueQrToken()}
                    className="w-full rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700 hover:bg-blue-100"
                  >
                    หมุนเวียน token ทันที
                  </button>
                </div>
              ) : (
                <div className="flex h-[260px] flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 text-center text-sm text-slate-500">
                  <p>
                    {session.status === "scheduled"
                      ? "ยังไม่เปิดเช็คชื่อ — กด “เปิดเช็คชื่อ” เพื่อแสดง QR"
                      : session.status === "paused"
                        ? "คาบอยู่ในสถานะหยุดชั่วคราว — กด “เปิดเช็คชื่อ (ดำเนินต่อ)” เพื่อแสดง QR อีกครั้ง"
                        : session.status_display}
                  </p>
                  {(session.status === "scheduled" || session.status === "paused") && (
                    <button
                      type="button"
                      onClick={() => void lifecycle("open")}
                      disabled={actionBusy}
                      className="mt-3 rounded-lg bg-emerald-600 px-4 py-2 font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                    >
                      เปิดเช็คชื่อ
                    </button>
                  )}
                </div>
              )}
            </div>

            <div className="mt-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-semibold text-slate-800">การควบคุมคาบ</h2>
              <div className="flex flex-wrap gap-2">
                {session.status === "open" && (
                  <button
                    type="button"
                    onClick={() => void lifecycle("pause")}
                    disabled={actionBusy}
                    className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                  >
                    ⏸ หยุดชั่วคราว
                  </button>
                )}
                {(session.status === "open" || session.status === "paused") && (
                  <button
                    type="button"
                    onClick={() => void lifecycle("close")}
                    disabled={actionBusy}
                    className="rounded-lg bg-slate-800 px-4 py-2 text-sm font-medium text-white hover:bg-slate-900 disabled:opacity-50"
                  >
                    ✓ ปิดคาบ (บันทึกขาดเรียนอัตโนมัติ)
                  </button>
                )}
                {(session.status === "scheduled" || session.status === "paused") && (
                  <button
                    type="button"
                    onClick={() => void lifecycle("open")}
                    disabled={actionBusy}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
                  >
                    ▶ เปิดเช็คชื่อ
                  </button>
                )}
                {session.status !== "closed" && session.status !== "cancelled" && (
                  <button
                    type="button"
                    onClick={() => void lifecycle("cancel")}
                    disabled={actionBusy}
                    className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                  >
                    ยกเลิกคาบ
                  </button>
                )}
              </div>
              <div className="mt-3 text-xs text-slate-500 tabular-nums">
                ลงทะเบียน {session.enrolled_count} คน · เช็คชื่อแล้ว {session.checked_in_count} คน
              </div>
            </div>
          </div>

          {/* Roster */}
          <div className="lg:col-span-3">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <h2 className="text-sm font-semibold text-slate-800">รายชื่อคาบเรียน</h2>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className={`${inputClass} max-w-[180px]`}
                  aria-label="กรองสถานะในรายชื่อ"
                >
                  <option value="">ทุกสถานะ</option>
                  <option value="present">เข้าเรียน</option>
                  <option value="late">มาสาย</option>
                  <option value="absent">ขาดเรียน</option>
                  <option value="excused">ลา/ได้รับอนุญาต</option>
                  <option value="not_checked_in">ยังไม่เช็คชื่อ</option>
                </select>
                <label className="ml-auto flex items-center gap-2 text-xs text-slate-500">
                  <input
                    type="checkbox"
                    checked={rosterAutoRefresh}
                    onChange={(e) => setRosterAutoRefresh(e.target.checked)}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  รีเฟรชอัตโนมัติทุก 5 วินาที
                </label>
              </div>
              <DataTable<RosterRow>
                columns={[
                  { key: "student_code", label: "รหัสนักศึกษา" },
                  { key: "student_name", label: "ชื่อ-นามสกุล" },
                  {
                    key: "checked_in_status",
                    label: "สถานะ",
                    render: (r) =>
                      r.checked_in_status ? (
                        <StatusBadge status={r.checked_in_status} />
                      ) : (
                        <StatusBadge status="scheduled" display="ยังไม่เช็คชื่อ" />
                      ),
                  },
                  {
                    key: "checked_in_at",
                    label: "เวลาที่เช็คชื่อ",
                    render: (r) => (r.checked_in_at ? new Date(r.checked_in_at).toLocaleTimeString("th-TH") : "-"),
                  },
                ]}
                rows={filteredRoster}
                loading={loading}
                emptyMessage="ไม่มีรายชื่อที่ตรงกับตัวกรอง"
                renderActions={(row) => (
                  <select
                    aria-label="แก้ไขสถานะรายคน"
                    value={recordByStudent.get(row.id)?.status ?? ""}
                    onChange={(e) => void editStatus(row, e.target.value)}
                    className="rounded-lg border border-slate-300 px-2 py-1 text-xs"
                  >
                    <option value="">— แก้สถานะ —</option>
                    <option value="present">เข้าเรียน</option>
                    <option value="late">มาสาย</option>
                    <option value="absent">ขาดเรียน</option>
                    <option value="excused">ลา/ได้รับอนุญาต</option>
                  </select>
                )}
              />
              <PaginationControls page={1} pages={1} count={roster.length} onChange={() => undefined} />
              <p className="mt-2 text-xs text-slate-500">
                แก้ไขสถานะต้องใส่เหตุผลและถูกบันทึก Audit Log (§14.3) — หลังปิดคาบ ทุกคนที่ไม่ได้เช็คชื่อกลายเป็นขาดเรียนอัตโนมัติ
              </p>
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
