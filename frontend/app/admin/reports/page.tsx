"use client";
/** Admin attendance report (spec §11 — uses shared ReportPanel). */
import AppShell from "@/components/AppShell";
import ReportPanel from "@/components/ReportPanel";
import { useRequireRole } from "@/lib/auth-context";

export default function AdminReportsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="รายงานอัตราการเข้าเรียน">
      {!user && null}
      <ReportPanel />
    </AppShell>
  );
}
