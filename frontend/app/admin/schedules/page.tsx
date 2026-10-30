"use client";
/** Class-schedule management (admin). Instructor variant: /instructor/schedules. */
import AppShell from "@/components/AppShell";
import CrudPage from "@/components/CrudPage";
import { scheduleColumns, scheduleFields, scheduleFilters } from "@/components/pageDefs";
import { useRequireRole } from "@/lib/auth-context";
import type { ClassSchedule } from "@/lib/types";

export default function AdminSchedulesPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการตารางเรียน">
      {!user && null}
      <CrudPage<ClassSchedule>
        title="ตารางเรียน"
        basePath="/class-schedules/"
        fields={scheduleFields}
        createTitle="เพิ่มสล็อตตารางเรียน"
        searchPlaceholder="ค้นหารายวิชา/ห้องเรียน…"
        emptyMessage="ยังไม่มีตารางเรียนในระบบ"
        columns={scheduleColumns}
        filters={scheduleFilters}
      />
    </AppShell>
  );
}
