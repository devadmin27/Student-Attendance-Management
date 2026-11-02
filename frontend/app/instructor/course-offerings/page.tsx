"use client";
/** Instructor course-offering management (รายวิชาที่ตนสอนเท่านั้น — scoped ฝั่ง backend). */
import AppShell from "@/components/AppShell";
import CrudPage from "@/components/CrudPage";
import { offeringColumns, offeringFields, offeringFilters } from "@/components/pageDefs";
import { useRequireRole } from "@/lib/auth-context";
import type { CourseOffering } from "@/lib/types";

export default function InstructorCourseOfferingsPage() {
  const user = useRequireRole(["instructor"]);
  return (
    <AppShell title="เปิดสอนรายวิชาของฉัน">
      {!user && null}
      <CrudPage<CourseOffering>
        title="เปิดสอนรายวิชา"
        basePath="/course-offerings/"
        fields={offeringFields}
        createTitle="เพิ่มการเปิดสอน"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อรายวิชา…"
        emptyMessage="ยังไม่มีรายวิชาที่คุณเปิดสอน"
        columns={offeringColumns}
        filters={offeringFilters}
        /* ลบได้เฉพาะรายวิชาที่ตนสอน (backend scope + ownership guard) —
           ถ้ามีการลงทะเบียน/คาบเช็คชื่อผูกอยู่ ระบบจะปิดสถานะเป็นยกเลิกแทน */
      />
    </AppShell>
  );
}
