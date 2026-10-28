"use client";
/** Public login page — SweetAlert2 feedback, role routing after login. */
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth, roleHome } from "@/lib/auth-context";
import { alertError } from "@/lib/swal";

export default function LoginPage() {
  const { user, loading, login } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Already authenticated → send to role home.
  useEffect(() => {
    if (!loading && user) {
      router.replace(roleHome(user.role));
    }
  }, [user, loading, router]);

  const onSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSubmitting(true);
    try {
      const loggedIn = await login(username, password);
      router.replace(roleHome(loggedIn.role));
    } catch (error) {
      await alertError(
        error instanceof Error && error.message ? error.message : "เข้าสู่ระบบไม่สำเร็จ",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-blue-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="text-2xl font-bold text-blue-900">SAMS</div>
          <div className="text-sm text-slate-500">
            Student Attendance Management System — เข้าสู่ระบบ
          </div>
        </div>
        <form
          onSubmit={(e) => void onSubmit(e)}
          className="space-y-4 rounded-2xl border border-slate-200 bg-white p-6 shadow-md"
        >
          <div className="flex flex-col gap-1">
            <label htmlFor="username" className="text-sm font-medium text-slate-700">
              ชื่อผู้ใช้
            </label>
            <input
              id="username"
              name="username"
              autoComplete="username"
              required
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              placeholder="เช่น admin, instructor01, s650001"
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="password" className="text-sm font-medium text-slate-700">
              รหัสผ่าน
            </label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            disabled={submitting || loading}
            className="w-full rounded-lg bg-blue-700 px-4 py-2.5 font-medium text-white hover:bg-blue-800 disabled:opacity-50"
          >
            {submitting ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}
          </button>
          <div className="flex items-center justify-between text-xs text-slate-500">
            <Link href="/" className="hover:text-blue-700">
              ← กลับหน้าแรก
            </Link>
            <span>
              ปลอดภัยด้วย JWT · Refresh Token แบบ HttpOnly Cookie
            </span>
          </div>
        </form>
      </div>
    </div>
  );
}
