"use client";
/** OIDC callback landing: after Keycloak redirect back, exchange refresh cookie for access token. */
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { refreshSession } from "@/lib/api";
import { useAuth, roleHome } from "@/lib/auth-context";
import { alertError } from "@/lib/swal";

const KEYCLOAK_ERROR_MESSAGES: Record<string, string> = {
  KEYCLOAK_DISABLED: "การเข้าสู่ระบบด้วย Keycloak ปิดใช้งานอยู่",
  KEYCLOAK_INVALID_STATE: "ข้อมูลการเข้าสู่ระบบไม่ถูกต้อง กรุณาลองใหม่",
  KEYCLOAK_INVALID_NONCE: "ข้อมูลการเข้าสู่ระบบไม่ถูกต้อง (nonce) กรุณาลองใหม่",
  KEYCLOAK_CODE_EXCHANGE_FAILED: "ไม่สามารถยืนยันตัวตนกับ Keycloak ได้ กรุณาลองใหม่",
  KEYCLOAK_TOKEN_INVALID: "โทเค็นจาก Keycloak ไม่ถูกต้อง",
  KEYCLOAK_CLAIMS_INVALID: "ข้อมูลผู้ใช้จาก Keycloak ไม่ครบถ้วน",
  KEYCLOAK_IDENTITY_NOT_LINKED: "ยังไม่มีการเชื่อมบัญชี Keycloak กับบัญชี SAMS กรุณาติดต่อผู้ดูแลระบบ",
  KEYCLOAK_AUTO_LINK_AMBIGUOUS: "พบอีเมลที่ตรงกับหลายบัญชี SAMS กรุณาติดต่อผู้ดูแลระบบเพื่อเชื่อมบัญชี",
  KEYCLOAK_AUTO_LINK_EMAIL_NOT_VERIFIED: "อีเมลจากบัญชีสถาบันยังไม่ได้ยืนยัน กรุณาติดต่อผู้ดูแลระบบหรือยืนยันอีเมลก่อน",
  KEYCLOAK_ACCOUNT_DISABLED: "บัญชีถูกระงับการใช้งาน",
  KEYCLOAK_ACCOUNT_STATUS_BLOCKED: "สถานะบัญชีไม่อนุญาตให้เข้าสู่ระบบ",
  KEYCLOAK_ROLE_NOT_ALLOWED: "บทบาทจาก Keycloak ไม่ได้รับอนุญาต",
  KEYCLOAK_IDP_UNAVAILABLE: "ระบบยืนยันตัวตน (Keycloak) ไม่พร้อมใช้งาน",
  KEYCLOAK_INVALID_REQUEST: "คำขอเข้าสู่ระบบไม่ถูกต้อง",
  KEYCLOAK_LOGIN_CANCELLED: "คุณยกเลิกการเข้าสู่ระบบด้วยบัญชีสถาบัน",
  KEYCLOAK_NOT_IMPLEMENTED: "ยังไม่เปิดใช้งานการเข้าสู่ระบบด้วย Keycloak ในระบบนี้ (รอการตั้งค่าเซิร์ฟเวอร์)",
};

function KeycloakCallbackContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { refreshHydration, user } = useAuth();
  const [status, setStatus] = useState<"working" | "done" | "error">("working");
  const [errorText, setErrorText] = useState<string>("");

  useEffect(() => {
    const err = searchParams.get("error");
    const nextParam = searchParams.get("next");
    const safeNext = nextParam && nextParam.startsWith("/") ? nextParam : null;

    if (err) {
      setStatus("error");
      const msg = KEYCLOAK_ERROR_MESSAGES[err] ?? `ไม่สามารถเข้าสู่ระบบด้วย Keycloak ได้ (${err})`;
      setErrorText(msg);
      void alertError("เข้าสู่ระบบไม่สำเร็จ", msg);
      return;
    }

    void (async () => {
      const ok = await refreshSession();
      if (!ok) {
        setStatus("error");
        const msg = "ไม่สามารถเริ่มเซสชันจาก Keycloak ได้ กรุณาลองใหม่";
        setErrorText(msg);
        await alertError("เข้าสู่ระบบไม่สำเร็จ", msg);
        return;
      }
      await refreshHydration();
      setStatus("done");
    })();
  }, [searchParams, refreshHydration]);

  useEffect(() => {
    if (status !== "done" || !user) return;
    const nextParam = searchParams.get("next");
    const safeNext = nextParam && nextParam.startsWith("/") ? nextParam : null;
    router.replace(safeNext ?? roleHome(user.role));
  }, [status, user, router, searchParams]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-white px-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-md">
        <div className="text-lg font-semibold text-slate-800">กำลังเข้าสู่ระบบผ่านบัญชีสถาบัน…</div>
        {status === "working" && (
          <p className="mt-2 text-sm text-slate-500">กรุณารอสักครู่</p>
        )}
        {status === "error" && (
          <>
            <p className="mt-3 text-sm text-red-700">{errorText}</p>
            <Link
              href="/login"
              className="mt-4 inline-block rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
            >
              กลับหน้าเข้าสู่ระบบ
            </Link>
          </>
        )}
        {status === "done" && !user && (
          <p className="mt-2 text-sm text-slate-500">กำลังโหลดข้อมูลผู้ใช้…</p>
        )}
      </div>
    </div>
  );
}

export default function KeycloakCallbackPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-white px-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-md">
            <div className="text-lg font-semibold text-slate-800">กำลังเข้าสู่ระบบผ่านบัญชีสถาบัน…</div>
            <p className="mt-2 text-sm text-slate-500">กรุณารอสักครู่</p>
          </div>
        </div>
      }
    >
      <KeycloakCallbackContent />
    </Suspense>
  );
}
