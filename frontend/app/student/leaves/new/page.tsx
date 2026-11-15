"use client";
/** New leave request (draft or save & submit). */
import AppShell from "@/components/AppShell";
import LeaveForm from "@/components/LeaveForm";
import { useRequireRole } from "@/lib/auth-context";

export default function NewLeavePage() {
  const user = useRequireRole(["student"]);
  return (
    <AppShell title="ยื่นใบลาใหม่">
      {!user && null}
      <LeaveForm />
    </AppShell>
  );
}
