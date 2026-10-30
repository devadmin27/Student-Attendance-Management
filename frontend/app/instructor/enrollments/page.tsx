"use client";
/** Instructor enrollment management (รายวิชาที่ตนสอนเท่านั้น — scoped ฝั่ง backend). */
import AppShell from "@/components/AppShell";
import CrudPage from "@/components/CrudPage";
import {
  BulkEnrollButton,
  enrollmentColumns,
  enrollmentFields,
  enrollmentFilters,
} from "@/components/pageDefs";
import { useRequireRole } from "@/lib/auth-context";
import type { Enrollment } from "@/lib/types";

export default function InstructorEnrollmentsPage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="การลงทะเบียนรายวิชาที่สอน">
      {!user && null}
      <CrudPage<Enrollment>
        title="การลงทะเบียน"
        basePath="/enrollments/"
        fields={enrollmentFields}
        createTitle="เพิ่มการลงทะเบียน"
        searchPlaceholder="ค้นหาด้วยรหัสนักศึกษา/ชื่อ…"
        emptyMessage="ยังไม่มีรายการลงทะเบียน"
        columns={enrollmentColumns}
        filters={enrollmentFilters}
        headerExtra={(refresh) => <BulkEnrollButton refresh={refresh} />}
      />
    </AppShell>
  );
}
