"use client";
/** Student enrolled courses (from dashboard payload). */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { EmptyState } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import type { StudentDashboardData } from "@/lib/types";

export default function StudentCoursesPage() {
  const user = useRequireRole(["student"]);
  const [courses, setCourses] = useState<StudentDashboardData["courses"]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<StudentDashboardData>({ url: "/dashboard/student/" });
        if (!cancelled) setCourses(data?.courses ?? []);
      } catch (error) {
        if (!cancelled) {
          await alertError("โหลดรายวิชาไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <AppShell title="รายวิชาที่ลงทะเบียน">
      {!user && null}
      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดรายวิชา…</p>
      ) : courses.length === 0 ? (
        <EmptyState message="ยังไม่มีรายวิชาที่ลงทะเบียนในภาคนี้" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {courses.map((course) => (
            <div key={course.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="text-base font-semibold text-slate-900">{course.course_code}</div>
              <div className="mt-0.5 text-sm text-slate-700">{course.course_name}</div>
              <div className="mt-2 text-xs text-slate-500">ภาคการศึกษา {course.term}</div>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
