"use client";
/**
 * Student QR check-in page.
 * Scans the rotating session QR (html5-qrcode) and posts the token plus
 * OPTIONAL device-location evidence to /attendance/check-in/ — the session
 * identity is derived server-side (§10.2). Location is fail-open: a refusal,
 * timeout or unsupported browser sends a status instead and never blocks the
 * check-in.
 */
import { useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { PageCard, StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDate, formatThaiTime } from "@/lib/format";
import { alertError, toastSuccess } from "@/lib/swal";
import type { CheckInResult } from "@/lib/types";

type LocationStatus = "denied" | "unavailable" | "unsupported";

type ResolvedLocation =
  | { latitude: number; longitude: number; accuracy: number }
  | { status: LocationStatus };

type LocationState = "idle" | "requesting" | "granted" | LocationStatus;

/** Visible feedback so the student can see the system actually asked. */
const LOCATION_HINT: Record<Exclude<LocationState, "idle">, string> = {
  requesting: "กำลังขอตำแหน่งอุปกรณ์… (ไม่ให้สิทธิ์ก็เช็คชื่อได้ตามปกติ)",
  granted: "ได้ตำแหน่งอุปกรณ์แล้ว — จะแนบเป็นหลักฐานตอนเช็คชื่อ",
  denied:
    "ไม่ได้รับสิทธิ์ตำแหน่ง — เช็คชื่อได้ตามปกติ (ถ้าต้องการบันทึก ให้เปิดสิทธิ์ตำแหน่งของเว็บนี้ในการตั้งค่าเบราว์เซอร์)",
  unavailable: "หาตำแหน่งอุปกรณ์ไม่ได้ — เช็คชื่อได้ตามปกติ",
  unsupported:
    "อุปกรณ์/เบราว์เซอร์นี้ไม่รองรับการขอตำแหน่ง (ต้องใช้ HTTPS) — เช็คชื่อได้ตามปกติ",
};

/** Best-effort device position; never throws — resolves a fail-open result. */
function locate(maxWaitMs = 8000): Promise<ResolvedLocation> {
  if (typeof navigator === "undefined" || !navigator.geolocation) {
    return Promise.resolve({ status: "unsupported" });
  }
  return new Promise((resolve) => {
    let done = false;
    const finish = (value: ResolvedLocation) => {
      if (!done) {
        done = true;
        resolve(value);
      }
    };
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        finish({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) =>
        finish(
          err.code === GeolocationPositionError.PERMISSION_DENIED
            ? { status: "denied" }
            : { status: "unavailable" },
        ),
      { enableHighAccuracy: true, timeout: maxWaitMs, maximumAge: 0 },
    );
  });
}

export default function StudentScanPage() {
  const user = useRequireRole(["student"]);
  const [scanning, setScanning] = useState(false);
  const [busy, setBusy] = useState(false);
  const [manualToken, setManualToken] = useState("");
  const [result, setResult] = useState<CheckInResult | null>(null);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [locating, setLocating] = useState(false);
  const [locationState, setLocationState] = useState<LocationState>("idle");
  const scannerRef = useRef<import("html5-qrcode").Html5Qrcode | null>(null);
  const handledRef = useRef(false);
  // Location lookup kicked off when the user starts scanning; consumed (and
  // cleared) at submit so every check-in captures a fresh fix. Manual-token
  // submissions fall back to requesting here if scanning was never started.
  const locationPromiseRef = useRef<Promise<ResolvedLocation> | null>(null);

  const requestLocation = () => {
    if (!locationPromiseRef.current) {
      setLocationState("requesting");
      locationPromiseRef.current = locate().then((result) => {
        setLocationState("latitude" in result ? "granted" : result.status);
        return result;
      });
    }
    return locationPromiseRef.current;
  };

  // Cleanup camera on unmount
  useEffect(
    () => () => {
      const scanner = scannerRef.current;
      if (scanner) {
        void scanner
          .stop()
          .then(() => scanner.clear())
          .catch(() => undefined);
        scannerRef.current = null;
      }
    },
    [],
  );

  const stopScanner = async () => {
    const scanner = scannerRef.current;
    if (scanner) {
      try {
        await scanner.stop();
        scanner.clear();
      } catch {
        // ignore — already stopped
      }
      scannerRef.current = null;
    }
    setScanning(false);
  };

  const submitToken = async (token: string) => {
    if (busy || handledRef.current) return;
    handledRef.current = true;
    setBusy(true);
    setLocating(true);
    try {
      // Fail-open device-location evidence: a refusal/timeout/unsupported
      // browser resolves a status and the check-in still goes through.
      const location = await requestLocation();
      locationPromiseRef.current = null; // next check-in captures a fresh fix
      const body: Record<string, unknown> = { token };
      if ("latitude" in location) {
        body.latitude = location.latitude;
        body.longitude = location.longitude;
        body.accuracy = location.accuracy;
      } else {
        body.location_status = location.status;
      }
      const { data, envelope } = await samsRequest<CheckInResult>({
        url: "/attendance/check-in/",
        method: "POST",
        data: body,
      });
      setResult(data);
      await toastSuccess(envelope.message);
    } catch (error) {
      if (error instanceof ApiError) {
        await alertError(error.message);
      } else {
        await alertError("เช็คชื่อไม่สำเร็จ — กรุณาลองอีกครั้ง");
      }
    } finally {
      setBusy(false);
      setLocating(false);
      setTimeout(() => {
        handledRef.current = false;
      }, 600);
    }
  };

  const startScan = async () => {
    setCameraError(null);
    // Ask for device location right away so the permission prompt appears
    // while the camera warms up (the fix is consumed at submit time).
    requestLocation();
    try {
      const { Html5Qrcode } = await import("html5-qrcode");
      const scanner = new Html5Qrcode("qr-reader", { verbose: false });
      scannerRef.current = scanner;
      setScanning(true);
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 240, height: 240 } },
        (decodedText) => {
          if (handledRef.current) return;
          void (async () => {
            await stopScanner();
            await submitToken(decodedText);
          })();
        },
        () => undefined, // per-frame decode miss — ignore
      );
    } catch (error) {
      setScanning(false);
      scannerRef.current = null;
      setCameraError(
        error instanceof Error && error.message.includes("Permission")
          ? "ไม่ได้รับอนุญาตให้ใช้กล้อง — กรุณาอนุญาตการเข้าถึงกล้องในเบราว์เซอร์ หรือใช้การกรอกรหัสด้วยตนเองด้านล่าง"
          : "เปิดกล้องไม่สำเร็จ — โปรดใช้การกรอกรหัสด้วยตนเองด้านล่าง หรือตรวจว่าอุปกรณ์มีกล้อง",
      );
    }
  };

  return (
    <AppShell title="สแกน QR Code เข้าเรียน">
      {!user && null}
      <div className="mx-auto max-w-xl space-y-4">
        <PageCard>
          <h2 className="mb-2 text-sm font-semibold text-slate-800">วิธีเช็คชื่อ</h2>
          <ol className="list-inside list-decimal space-y-1 text-sm text-slate-600">
            <li>อาจารย์จะแสดง QR Code บนจอในห้องเรียน (token หมดอายุและหมุนเวียนตามเวลาจริง)</li>
            <li>กด “เริ่มสแกน” แล้วเล็งกล้องไปที่ QR — ระบบจะส่ง token ให้เซิร์ฟเวอร์ตรวจสอบทันที</li>
            <li>สถานะ presentation/มาสาย คำนวณจากเวลาที่คุณเช็คชื่อจริง</li>
          </ol>
        </PageCard>

        <PageCard>
          <div className="flex flex-col items-center gap-3">
            <div
              id="qr-reader"
              className={`w-full max-w-sm overflow-hidden rounded-xl ${scanning ? "border-2 border-blue-300 bg-slate-900" : "hidden"}`}
            />
            {!scanning && (
              <div className="flex h-52 w-full max-w-sm items-center justify-center rounded-xl border border-dashed border-slate-300 text-sm text-slate-500">
                กล้องยังไม่ทำงาน
              </div>
            )}
            {!scanning ? (
              <button
                type="button"
                onClick={() => void startScan()}
                disabled={busy}
                className="rounded-xl bg-blue-700 px-6 py-3 font-medium text-white shadow hover:bg-blue-800 disabled:opacity-50"
              >
                📷 เริ่มสแกน
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void stopScanner()}
                className="rounded-xl border border-slate-300 px-6 py-3 font-medium text-slate-700 hover:bg-slate-50"
              >
                หยุดสแกน
              </button>
            )}
            {cameraError && <p className="text-center text-xs text-amber-700">{cameraError}</p>}
            {busy && <p className="text-sm text-slate-500">{locating ? "กำลังขอตำแหน่งอุปกรณ์… (ไม่ยินยอมกดเช็คชื่อได้อยู่)" : "กำลังส่งข้อมูลเช็คชื่อ…"}</p>}
            {!busy && locationState !== "idle" && (
              <p className="text-center text-xs text-slate-500">{LOCATION_HINT[locationState]}</p>
            )}
          </div>
        </PageCard>

        <PageCard>
          <h2 className="mb-2 text-sm font-semibold text-slate-800">กรอกรหัสด้วยตนเอง (ถ้าสแกนไม่ได้)</h2>
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              const token = manualToken.trim();
              if (!token) return;
              void submitToken(token);
            }}
          >
            <input
              type="text"
              value={manualToken}
              onChange={(e) => setManualToken(e.target.value)}
              onChangeCapture={() => setResult(null)}
              placeholder="วาง token จาก QR…"
              autoComplete="off"
              className="flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
            />
            <button
              type="submit"
              disabled={busy || manualToken.trim() === ""}
              className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
            >
              เช็คชื่อ
            </button>
          </form>
          <p className="mt-2 text-xs text-slate-500">
            token ใช้ได้เฉพาะเซสชันเปิดอยู่และหมดอายุตาม TTL — ระบบบันทึกซ้ำไม่ได้ (409 ATTENDANCE_ALREADY_EXISTS)
          </p>
        </PageCard>

        {result && (
          <PageCard className="border-emerald-200 bg-emerald-50">
            <div className="space-y-2 text-sm text-emerald-900">
              <h2 className="font-semibold">ผลการเช็คชื่อ</h2>
              <div>
                <strong>{result.course_code}</strong> — {result.course_name}
              </div>
              <div>วันเรียน {formatThaiDate(result.session_date)}</div>
              <div className="flex items-center gap-2">
                สถานะของคุณ: <StatusBadge status={result.status} />
              </div>
              <div className="text-xs text-emerald-700">เวลาที่บันทึก: {formatThaiTime(result.checked_in_at)}</div>
            </div>
          </PageCard>
        )}
      </div>
    </AppShell>
  );
}
