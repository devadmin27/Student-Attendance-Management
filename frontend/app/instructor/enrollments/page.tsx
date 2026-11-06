"use client";
/** Instructor enrollment management (รายวิชาที่ตนสอนเท่านั้น — scoped ฝั่ง backend). */
import AppShell from "@/components/AppShell";
import EnrollmentPanel from "@/components/EnrollmentPanel";
import { useRequireRole } from "@/lib/auth-context";

export default function InstructorEnrollmentsPage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="การลงทะเบียนรายวิชาที่สอน">
      {!user && null}
      <EnrollmentPanel createTitle="เพิ่มการลงทะเบียน" />
    </AppShell>
  );
}
