"use client";
/** Edit a draft leave request. */
import { Suspense } from "react";
import { useParams } from "next/navigation";
import AppShell from "@/components/AppShell";
import LeaveForm from "@/components/LeaveForm";
import { useRequireRole } from "@/lib/auth-context";

export default function EditLeavePage() {
  return (
    <Suspense
      fallback={
        <div className="p-10 text-center text-sm text-slate-500">กำลังโหลด…</div>
      }
    >
      <EditLeaveContent />
    </Suspense>
  );
}

function EditLeaveContent() {
  const user = useRequireRole(["student"]);
  const params = useParams<{ id: string }>();
  return (
    <AppShell title="แก้ไขคำร้องลา">
      {!user && null}
      <LeaveForm requestId={params.id} />
    </AppShell>
  );
}
