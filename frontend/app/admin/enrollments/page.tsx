"use client";
/** Enrollment management (admin). Instructor variant: /instructor/enrollments. */
import AppShell from "@/components/AppShell";
import EnrollmentPanel from "@/components/EnrollmentPanel";
import { useRequireRole } from "@/lib/auth-context";

export default function AdminEnrollmentsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการการลงทะเบียนเรียน">
      {!user && null}
      <EnrollmentPanel />
    </AppShell>
  );
}
