"use client";
/**
 * Instructor attendance control room.
 * - Session lifecycle (open → pause → close / cancel)
 * - Rotating QR token displayed on-screen; re-issues automatically before expiry
 * - Live roster (polls every few seconds) + audited manual status edit
 */
import Link from "next/link";
import {
  Suspense,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import { useParams } from "next/navigation";
import QRCode from "react-qr-code";
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiTime } from "@/lib/format";
import { alertError, confirmDialog, promptReason, toastSuccess } from "@/lib/swal";
import type { AttendanceSession, QRTokenInfo, RosterRow } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

// ขนาด QR: ค่าเริ่มต้นใหญ่เป็น 2 เท่าของเดิม (190 → 380) และให้ผู้ใช้ปรับเองได้
// การ์ด QR กว้างตามขนาดที่เลือก (ไม่ใช่คอลัมน์กริดคงที่) เพื่อให้ขนาดจริงตรงกับที่ตั้งไว้
const QR_SIZE_DEFAULT = 380;
const QR_SIZE_MIN = 160;
const QR_SIZE_MAX = 480;
const QR_SIZE_STEP = 20;
const QR_SIZE_STORAGE_KEY = "sams.qr-size";
// ความกว้างการ์ดที่ต้องเผื่อให้ QR: border 2 + p-4 32 + p-3 24 + p-2 16 = 74px + เผื่อ 2px
const QR_PANEL_EXTRA = 76;
const QR_PANEL_MIN_WIDTH = 320;

// ---- Live roster polling ----
// ถี่เฉพาะตอนเปิดเช็คชื่อและอยู่ในหน้าต่างเวลา; นอกนั้นลดความถี่ลงมาก
// และหยุดสนิทเมื่อปิด/ยกเลิกคาบ, ปิด auto-refresh หรือซ่อนแท็บ
const POLL_OPEN_IN_WINDOW_MS = 5_000;
const POLL_OPEN_OUT_OF_WINDOW_MS = 25_000;
const POLL_PENDING_MS = 15_000;
// 429 backoff: 10 → 20 → 40 → 60 วินาที (คงที่ที่ 60 หลังจากนั้น)
const POLL_RATE_LIMIT_BACKOFF_MS = [10_000, 20_000, 40_000, 60_000];
// QR re-issue backoff เมื่อออก token ไม่สำเร็จ: 5 → 10 → 20 → 30 วินาที
const QR_REISSUE_BACKOFF_MS = [5_000, 10_000, 20_000, 30_000];
const ONE_SHOT_REISSUE_MARGIN = 2; // seconds before expiry

function rosterPollInterval(session: AttendanceSession): number {
  if (session.status !== "open") return POLL_PENDING_MS;
  const now = Date.now();
  const start = new Date(session.check_in_start).getTime();
  const end = new Date(
    session.check_in_effective_end ?? session.check_in_end,
  ).getTime();
  if (Number.isFinite(start) && Number.isFinite(end) && now >= start && now <= end) {
    return POLL_OPEN_IN_WINDOW_MS;
  }
  return POLL_OPEN_OUT_OF_WINDOW_MS;
}

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
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<QRTokenInfo | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(0);
  const [actionBusy, setActionBusy] = useState(false);
  const [rosterAutoRefresh, setRosterAutoRefresh] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  // อ่านขนาด QR ที่ผู้ใช้ปรับไว้ตั้งแต่ต้น (เฉพาะฝั่งเบราว์เซอร์) — ค่านี้
  // ไม่ได้ถูก render ก่อนโหลด session เสร็จ จึงไม่เกิด hydration mismatch
  const [qrSize, setQrSize] = useState(() => {
    if (typeof window === "undefined") return QR_SIZE_DEFAULT;
    const saved = Number(window.localStorage.getItem(QR_SIZE_STORAGE_KEY));
    return Number.isFinite(saved) && saved >= QR_SIZE_MIN && saved <= QR_SIZE_MAX
      ? saved
      : QR_SIZE_DEFAULT;
  });

  // Polling/backoff state — refs hold values read inside timers (no re-render
  // needed) while `pollSeq` re-arms the self-scheduling poll loop.
  const [pollError, setPollError] = useState<string | null>(null);
  const [pollBackoffMs, setPollBackoffMs] = useState(0);
  const [pollSeq, setPollSeq] = useState(0);
  const pollBackoffIndexRef = useRef(0);
  const [isVisible, setIsVisible] = useState(() =>
    typeof document === "undefined" ? true : document.visibilityState === "visible",
  );

  // QR re-issue guards: a failed issue must not retry every second.
  const [qrError, setQrError] = useState<string | null>(null);
  const qrIssuingRef = useRef(false);
  const qrFailureCountRef = useRef(0);
  const qrRetryAtRef = useRef(0);

  const updateQrSize = (next: number) => {
    const clamped = Math.min(QR_SIZE_MAX, Math.max(QR_SIZE_MIN, next));
    setQrSize(clamped);
    window.localStorage.setItem(QR_SIZE_STORAGE_KEY, String(clamped));
  };

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

  const loadRoster = useCallback(
    async (silent = false): Promise<{ ok: boolean; status?: number }> => {
      try {
        const { data } = await samsRequest<RosterRow[]>({
          url: `/attendance/sessions/${sessionId}/roster/`,
        });
        setRoster(data ?? []);
        setPollError(null);
        return { ok: true };
      } catch (error) {
        const status = error instanceof ApiError ? error.status : undefined;
        if (silent) {
          // Polling failures get an inline banner instead of a modal alert,
          // so a transient 429 cannot spam the instructor every few seconds.
          setPollError(
            status === 429
              ? "ระบบจำกัดจำนวนคำขอชั่วคราว — กำลังลองใหม่ด้วยความถี่ที่ต่ำลง"
              : "อัปเดตรายชื่อไม่สำเร็จ — ระบบจะลองใหม่ให้อัตโนมัติ",
          );
        } else {
          await alertError(
            "โหลดรายชื่อคาบไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
        return { ok: false, status };
      }
    },
    [sessionId],
  );

  const issueQrToken = useCallback(
    async (silent = false) => {
      // Single-flight + backoff: a failing re-issue must not fire every second.
      if (qrIssuingRef.current) return null;
      qrIssuingRef.current = true;
      try {
        const { data, envelope } = await samsRequest<QRTokenInfo>({
          url: `/attendance/sessions/${sessionId}/qr-token/`,
          method: "POST",
          data: {},
        });
        setToken(data);
        const remaining = Math.max(1, Number(data.expires_in_seconds ?? 30));
        setSecondsLeft(remaining);
        qrFailureCountRef.current = 0;
        qrRetryAtRef.current = 0;
        setQrError(null);
        if (!silent) {
          void toastSuccess(envelope.message ?? "ออก QR Code สำเร็จ");
        }
        return data;
      } catch (error) {
        const status = error instanceof ApiError ? error.status : undefined;
        const attempt = Math.min(
          qrFailureCountRef.current,
          QR_REISSUE_BACKOFF_MS.length - 1,
        );
        qrRetryAtRef.current = Date.now() + QR_REISSUE_BACKOFF_MS[attempt];
        qrFailureCountRef.current = Math.min(
          attempt + 1,
          QR_REISSUE_BACKOFF_MS.length - 1,
        );
        setQrError(
          status === 429
            ? "ระบบจำกัดจำนวนคำขอชั่วคราว — QR จะหมุนเวียนใหม่เมื่อทำได้"
            : "ออก Token ใหม่ไม่สำเร็จ — ระบบจะลองใหม่ให้อัตโนมัติ",
        );
        if (!silent) {
          await alertError(
            "ออก QR Code ไม่สำเร็จ",
            error instanceof ApiError ? error.message : undefined,
          );
        }
        return null;
      } finally {
        qrIssuingRef.current = false;
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

  // Pause polling while the tab is hidden; resume when it becomes visible.
  useEffect(() => {
    const onChange = () => setIsVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onChange);
    return () => document.removeEventListener("visibilitychange", onChange);
  }, []);

  // Adaptive live roster polling. One self-scheduling timeout at a time:
  // - open + inside check-in window: 5s
  // - open but outside the window: 25s
  // - scheduled/paused: 15s
  // - closed/cancelled, hidden tab, or auto-refresh off: no polling
  // - 429: 10 → 20 → 40 → 60s backoff before trying again
  useEffect(() => {
    if (!rosterAutoRefresh || !session || !isVisible) return;
    if (session.status === "closed" || session.status === "cancelled") return;

    const delay =
      pollBackoffMs > 0 ? pollBackoffMs : rosterPollInterval(session);
    const timer = setTimeout(async () => {
      const result = await loadRoster(true);
      if (result.ok) {
        pollBackoffIndexRef.current = 0;
        setPollBackoffMs(0);
      } else if (result.status === 429) {
        const index = Math.min(
          pollBackoffIndexRef.current,
          POLL_RATE_LIMIT_BACKOFF_MS.length - 1,
        );
        setPollBackoffMs(POLL_RATE_LIMIT_BACKOFF_MS[index]);
        pollBackoffIndexRef.current = Math.min(
          index + 1,
          POLL_RATE_LIMIT_BACKOFF_MS.length - 1,
        );
      } else {
        setPollBackoffMs(0);
      }
      setPollSeq((n) => n + 1);
    }, delay);

    return () => clearTimeout(timer);
  }, [
    rosterAutoRefresh,
    session,
    isVisible,
    pollBackoffMs,
    pollSeq,
    loadRoster,
  ]);

  // QR token countdown. It deliberately runs slightly past zero while a
  // re-issue is failing, so the retry effect below keeps ticking.
  useEffect(() => {
    if (!token || !session || session.status !== "open") return;
    const interval = setInterval(() => {
      setSecondsLeft((prev) => prev - 1);
    }, 1000);
    return () => clearInterval(interval);
  }, [token, session]);

  // Rotate shortly before expiry, respecting the re-issue backoff.
  useEffect(() => {
    if (!token || !session || session.status !== "open") return;
    if (secondsLeft > ONE_SHOT_REISSUE_MARGIN) return;
    if (Date.now() < qrRetryAtRef.current) return;
    void issueQrToken(true);
  }, [secondsLeft, token, session, issueQrToken]);

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
      // A manual lifecycle action resets any poll/QR backoff immediately.
      pollBackoffIndexRef.current = 0;
      setPollBackoffMs(0);
      if (action === "open") {
        await issueQrToken(true);
      } else {
        setToken(null);
        setQrError(null);
        setSecondsLeft(0);
        qrFailureCountRef.current = 0;
        qrRetryAtRef.current = 0;
      }
      await loadRoster(true);
    } catch (error) {
      await alertError(
        "จัดการคาบไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setActionBusy(false);
    }
  };

  const editStatus = async (row: RosterRow, nextStatus: string) => {
    if (!nextStatus) return;
    if (!row.record_id) {
      await alertError(
        "นักศึกษายังไม่มีรายการเช็คชื่อในคาบนี้ เช็คชื่อ (หรือรอปิดคาบสร้างรายการขาดเรียน) ก่อนจึงจะแก้ไขสถานะได้",
      );
      return;
    }
    const reason = await promptReason("เหตุผลการแก้ไขสถานะ (บันทึกลง Audit Log)");
    if (!reason) return;
    try {
      await samsRequest({
        url: `/attendance/records/${row.record_id}/`,
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

  // นับจาก roster ที่เพิ่งโหลด เพื่อให้ตัวเลขอัปเดตตามการ poll โดยไม่ต้อง
  // โหลด session ซ้ำ (ระหว่างที่ roster ยังว่างให้ใช้ค่าจาก session)
  const checkedInCount = useMemo(
    () =>
      roster.length > 0
        ? roster.filter((r) => r.checked_in_status !== null).length
        : session?.checked_in_count ?? 0,
    [roster, session],
  );

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

        <div className="flex flex-col gap-4 xl:flex-row">
          {/* QR display */}
          <div
            className="xl:w-[var(--qr-panel-width)] xl:shrink-0"
            style={
              {
                "--qr-panel-width": `${Math.max(QR_PANEL_MIN_WIDTH, qrSize + QR_PANEL_EXTRA)}px`,
              } as CSSProperties
            }
          >
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-sm font-semibold text-slate-800">QR Code เช็คชื่อ (Rotating Token)</h2>
              <p className="mb-3 text-xs text-slate-500">
                Token หมุนเวียนอัตโนมัติก่อนหมดอายุ — ระบบเก็บเฉพาะ SHA-256 hash ไม่เก็บ plaintext
              </p>
              {session.status === "open" ? (
                <div className="space-y-3">
                  <div className="flex justify-center rounded-xl bg-slate-50 p-3">
                    {token ? (
                      <div className="flex w-full max-w-full flex-col items-center gap-3">
                        <div className="w-full rounded-lg bg-white p-2 shadow-sm">
                          <QRCode
                            value={token.qr}
                            size={qrSize}
                            style={{
                              width: "100%",
                              height: "auto",
                              maxWidth: `${qrSize}px`,
                              display: "block",
                              margin: "0 auto",
                            }}
                          />
                        </div>
                        <div className="text-center text-xs text-slate-500">
                          {Math.max(0, secondsLeft) > 0 ? (
                            <>
                              หมดอายุในอีก{" "}
                              <strong className="tabular-nums text-slate-800">
                                {Math.max(0, secondsLeft)}s
                              </strong>{" "}
                              · ระบบจะหมุนเวียน token ใหม่เอง
                            </>
                          ) : (
                            <>Token หมดอายุแล้ว — กำลังออก token ใหม่…</>
                          )}
                        </div>
                        {qrError && (
                          <p
                            role="status"
                            className="w-full rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-center text-xs text-amber-800"
                          >
                            {qrError}
                          </p>
                        )}
                        <div className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2">
                          <div className="flex items-center justify-between text-xs text-slate-600">
                            <label htmlFor="qr-size" className="font-medium">
                              ขนาด QR Code
                            </label>
                            <span className="tabular-nums font-semibold text-slate-800">{qrSize}px</span>
                          </div>
                          <div className="mt-2 flex items-center gap-2">
                            <button
                              type="button"
                              aria-label="ลดขนาด QR Code"
                              onClick={() => updateQrSize(qrSize - QR_SIZE_STEP)}
                              disabled={qrSize <= QR_SIZE_MIN}
                              className="h-7 w-7 shrink-0 rounded-md border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                            >
                              −
                            </button>
                            <input
                              id="qr-size"
                              type="range"
                              min={QR_SIZE_MIN}
                              max={QR_SIZE_MAX}
                              step={QR_SIZE_STEP}
                              value={qrSize}
                              onChange={(e) => updateQrSize(Number(e.target.value))}
                              className="h-2 min-w-0 flex-1 cursor-pointer accent-blue-700"
                            />
                            <button
                              type="button"
                              aria-label="เพิ่มขนาด QR Code"
                              onClick={() => updateQrSize(qrSize + QR_SIZE_STEP)}
                              disabled={qrSize >= QR_SIZE_MAX}
                              className="h-7 w-7 shrink-0 rounded-md border border-slate-300 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40"
                            >
                              +
                            </button>
                            <button
                              type="button"
                              onClick={() => updateQrSize(QR_SIZE_DEFAULT)}
                              className="shrink-0 rounded-md border border-slate-300 px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
                            >
                              รีเซ็ต
                            </button>
                          </div>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="flex aspect-square w-full animate-pulse items-center justify-center rounded bg-slate-200 text-sm text-slate-500"
                        style={{ maxWidth: qrSize }}
                      >
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
                ลงทะเบียน {session.enrolled_count} คน · เช็คชื่อแล้ว {checkedInCount} คน
              </div>
            </div>
          </div>

          {/* Roster */}
          <div className="min-w-0 xl:flex-1">
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
                    onChange={(e) => {
                      setRosterAutoRefresh(e.target.checked);
                      if (e.target.checked) {
                        pollBackoffIndexRef.current = 0;
                        setPollBackoffMs(0);
                      }
                    }}
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  รีเฟรชอัตโนมัติ
                </label>
              </div>
              {pollError && (
                <div
                  role="status"
                  className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800"
                >
                  {pollError}
                </div>
              )}
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
                    value={row.checked_in_status ?? ""}
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
