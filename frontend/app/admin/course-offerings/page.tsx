"use client";
/** Course-offering management (admin). Instructor variant: /instructor/course-offerings. */
import AppShell from "@/components/AppShell";
import CrudPage from "@/components/CrudPage";
import {
  offeringColumns,
  offeringFields,
  offeringFilters,
} from "@/components/pageDefs";
import { useRequireRole } from "@/lib/auth-context";
import type { CourseOffering } from "@/lib/types";

export default function AdminCourseOfferingsPage() {
  const user = useRequireRole(["admin"]);
  return (
    <AppShell title="จัดการเปิดสอนรายวิชา">
      {!user && null}
      <CrudPage<CourseOffering>
        title="เปิดสอนรายวิชา"
        basePath="/course-offerings/"
        fields={offeringFields}
        createTitle="เพิ่มการเปิดสอน"
        searchPlaceholder="ค้นหาด้วยรหัส/ชื่อรายวิชา…"
        emptyMessage="ยังไม่มีการเปิดสอนรายวิชา"
        columns={offeringColumns}
        filters={offeringFilters}
      />
    </AppShell>
  );
}
