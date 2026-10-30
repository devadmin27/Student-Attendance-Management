"use client";
/** Enrollment management (admin). Instructor variant: /instructor/enrollments. */
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

export default function AdminEnrollmentsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการการลงทะเบียนเรียน">
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
