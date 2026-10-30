"use client";
/** Instructor class-schedule management (ตารางของรายวิชาที่ตนสอน — scoped ฝั่ง backend). */
import AppShell from "@/components/AppShell";
import CrudPage from "@/components/CrudPage";
import { scheduleColumns, scheduleFields, scheduleFilters } from "@/components/pageDefs";
import { useRequireRole } from "@/lib/auth-context";
import type { ClassSchedule } from "@/lib/types";

export default function InstructorSchedulesPage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="ตารางเรียนรายวิชาที่สอน">
      {!user && null}
      <CrudPage<ClassSchedule>
        title="ตารางเรียน"
        basePath="/class-schedules/"
        fields={scheduleFields}
        createTitle="เพิ่มสล็อตตารางเรียน"
        searchPlaceholder="ค้นหารายวิชา/ห้องเรียน…"
        emptyMessage="ยังไม่มีตารางเรียนของรายวิชาที่คุณสอน"
        columns={scheduleColumns}
        filters={scheduleFilters}
      />
    </AppShell>
  );
}
