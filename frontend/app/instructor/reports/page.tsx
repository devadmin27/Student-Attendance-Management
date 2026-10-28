"use client";
/** Instructor attendance report (server scopes to own offerings). */
import AppShell from "@/components/AppShell";
import ReportPanel from "@/components/ReportPanel";
import { useRequireRole } from "@/lib/auth-context";

export default function InstructorReportsPage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="รายงานอัตราการเข้าเรียน (รายวิชาของฉัน)">
      {!user && null}
      <ReportPanel />
    </AppShell>
  );
}
