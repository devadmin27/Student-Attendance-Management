"use client";
/** Instructor course-offering overview (read-only, scoped by backend). */
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import { useEffect, useState } from "react";
import type { CourseOffering } from "@/lib/types";

export default function InstructorCoursesPage() {
  const user = useRequireRole(["instructor"]);
  const [rows, setRows] = useState<CourseOffering[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data, envelope } = await samsRequest<CourseOffering[]>({
          url: "/course-offerings/",
          params: { page, page_size: 20 },
        });
        if (cancelled) return;
        setRows(data ?? []);
        setPages(envelope.pagination?.pages ?? 1);
        setCount(envelope.pagination?.count ?? (data?.length ?? 0));
      } catch (error) {
        if (!cancelled) {
          setRows([]);
          await alertError("โหลดรายวิชาไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page]);

  return (
    <AppShell title="รายวิชาที่รับผิดชอบ">
      {!user && null}
      <DataTable<CourseOffering>
        columns={[
          { key: "course_code", label: "รหัสรายวิชา" },
          { key: "course_name", label: "ชื่อรายวิชา" },
          { key: "term_label", label: "ภาคการศึกษา" },
          { key: "enrollment_count", label: "จำนวนลงทะเบียน", className: "tabular-nums" },
          { key: "status", label: "สถานะ", render: (row) => <StatusBadge status={row.status} /> },
        ]}
        rows={rows}
        loading={loading}
        emptyMessage="ยังไม่มีรายวิชาที่รับผิดชอบในภาคนี้"
      />
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />
    </AppShell>
  );
}
