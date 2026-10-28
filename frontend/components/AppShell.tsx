"use client";
import Link from "next/link";
import { useState } from "react";
import { useAuth, type Role } from "@/lib/auth-context";

interface MenuItem {
  href: string;
  label: string;
  icon: string;
}

const ADMIN_MENU: MenuItem[] = [
  { href: "/admin/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/admin/users", label: "จัดการผู้ใช้งาน", icon: "👥" },
  { href: "/admin/students", label: "จัดการนักศึกษา", icon: "🎓" },
  { href: "/admin/instructors", label: "จัดการอาจารย์", icon: "🧑‍🏫" },
  { href: "/admin/programs", label: "จัดการหลักสูตร", icon: "🏅" },
  { href: "/admin/class-groups", label: "จัดการกลุ่มเรียน", icon: "🏫" },
  { href: "/admin/academic-terms", label: "จัดการภาคการศึกษา", icon: "📅" },
  { href: "/admin/courses", label: "จัดการรายวิชา", icon: "📘" },
  { href: "/admin/course-offerings", label: "จัดการเปิดสอนรายวิชา", icon: "📚" },
  { href: "/admin/enrollments", label: "จัดการการลงทะเบียน", icon: "🗒️" },
  { href: "/admin/schedules", label: "จัดการตารางเรียน", icon: "⏰" },
  { href: "/admin/attendance-sessions", label: "คาบเรียนเช็คชื่อ", icon: "🟢" },
  { href: "/admin/attendance-records", label: "รายการเช็คชื่อ", icon: "✅" },
  { href: "/admin/reports", label: "รายงานการเข้าเรียน", icon: "📈" },
  { href: "/admin/audit-logs", label: "Audit Logs", icon: "📝" },
];

const INSTRUCTOR_MENU: MenuItem[] = [
  { href: "/instructor/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/instructor/attendance", label: "เปิดเช็คชื่อ", icon: "🟢" },
  { href: "/instructor/courses", label: "รายวิชาของฉัน", icon: "📘" },
  { href: "/instructor/schedule", label: "ตารางสอน", icon: "⏰" },
  { href: "/instructor/reports", label: "รายงานการเข้าเรียน", icon: "📈" },
];

const STUDENT_MENU: MenuItem[] = [
  { href: "/student/dashboard", label: "Dashboard", icon: "📊" },
  { href: "/student/scan", label: "สแกน QR Code", icon: "📷" },
  { href: "/student/courses", label: "รายวิชาที่ลงทะเบียน", icon: "📘" },
  { href: "/student/schedule", label: "ตารางเรียน", icon: "⏰" },
  { href: "/student/history", label: "ประวัติการเช็คชื่อ", icon: "✅" },
  { href: "/student/profile", label: "โปรไฟล์", icon: "👤" },
];

const MENU_BY_ROLE: Record<Role, MenuItem[]> = {
  admin: ADMIN_MENU,
  instructor: INSTRUCTOR_MENU,
  student: STUDENT_MENU,
};

export default function AppShell({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  const { user, logout, loading } = useAuth();
  const [drawerOpen, setDrawerOpen] = useState(false);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-pulse text-slate-500">กำลังโหลดระบบ…</div>
      </div>
    );
  }

  const menu = user ? MENU_BY_ROLE[user.role] : [];

  const sidebar = (
    <nav className="flex flex-col gap-1 p-3">
      <div className="px-3 py-4">
        <div className="text-lg font-bold text-blue-900">SAMS</div>
        <div className="text-xs text-slate-500">Student Attendance Mgmt. System</div>
      </div>
      {menu.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          onClick={() => setDrawerOpen(false)}
          className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-700 hover:bg-blue-50 hover:text-blue-800"
        >
          <span aria-hidden>{item.icon}</span>
          {item.label}
        </Link>
      ))}
      <button
        type="button"
        onClick={() => void logout()}
        className="mt-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
      >
        🚪 ออกจากระบบ
      </button>
    </nav>
  );

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 overflow-y-auto border-r border-slate-200 bg-white lg:block">
        {sidebar}
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="ปิดเมนู"
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-72 bg-white shadow-lg">
            {sidebar}
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="เปิดเมนู"
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 lg:hidden"
              onClick={() => setDrawerOpen(true)}
            >
              ☰
            </button>
            <h1 className="text-base font-semibold text-slate-900 md:text-lg">{title}</h1>
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-slate-500 md:inline">
                {user.profile?.first_name ?? user.username} ({user.role_th})
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm text-white hover:bg-blue-800"
              >
                ออกจากระบบ
              </button>
            </div>
          )}
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6">{children}</main>
        <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-400">
          SAMS v1.0.0 — Student Attendance Management System
        </footer>
      </div>
    </div>
  );
}
