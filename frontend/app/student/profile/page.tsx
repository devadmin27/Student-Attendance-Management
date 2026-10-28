"use client";
/** Student profile (read-only — self-edit endpoint is intentionally not exposed). */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import { PageCard, StatusBadge } from "@/components/ui";
import { useRequireRole, useAuth } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { alertError } from "@/lib/swal";
import type { StudentDashboardData } from "@/lib/types";

export default function StudentProfilePage() {
  const user = useRequireRole(["student"]);
  const { user: authUser } = useAuth();
  const [profile, setProfile] = useState<StudentDashboardData["profile"]>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { data } = await samsRequest<StudentDashboardData>({ url: "/dashboard/student/" });
        if (!cancelled) setProfile(data?.profile ?? null);
      } catch (error) {
        if (!cancelled) {
          await alertError("โหลดโปรไฟล์ไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
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
    <AppShell title="โปรไฟล์ของฉัน">
      {!user && null}
      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังโหลดโปรไฟล์…</p>
      ) : (
        <div className="mx-auto max-w-xl space-y-4">
          <PageCard>
            <h2 className="mb-4 text-sm font-semibold text-slate-800">ข้อมูลนักศึกษา</h2>
            <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
              <dt className="text-slate-500">รหัสนักศึกษา</dt>
              <dd className="font-medium text-slate-900">{profile?.student_code ?? "-"}</dd>
              <dt className="text-slate-500">ชื่อ-นามสกุล</dt>
              <dd className="font-medium text-slate-900">
                {profile ? `${profile.first_name} ${profile.last_name}` : "-"}
              </dd>
              <dt className="text-slate-500">ชื่อผู้ใช้</dt>
              <dd>{profile?.username ?? authUser?.username ?? "-"}</dd>
              <dt className="text-slate-500">อีเมล</dt>
              <dd>{profile?.email || "-"}</dd>
              <dt className="text-slate-500">หลักสูตร</dt>
              <dd>{profile?.program_name ?? "-"}</dd>
              <dt className="text-slate-500">กลุ่มเรียน</dt>
              <dd>{profile?.class_group_name ?? "-"}</dd>
              <dt className="text-slate-500">ชั้นปี</dt>
              <dd>{profile?.academic_year_level ?? "-"}</dd>
              <dt className="text-slate-500">สถานะ</dt>
              <dd className="flex items-center gap-2">
                {profile ? (
                  <>
                    <StatusBadge status={profile.status} />
                    <span>{profile.status_display}</span>
                  </>
                ) : (
                  "-"
                )}
              </dd>
            </dl>
          </PageCard>
          <p className="text-xs text-slate-500">
            ข้อมูลโปรไฟล์ถูกจัดการโดยผู้ดูแลระบบ (การปกป้องข้อมูลส่วนบุคคล PDPA) — หากข้อมูลไม่ถูกต้อง กรุณาแจ้งสำนักทะเบียนหรือผู้ดูแลระบบ
          </p>
        </div>
      )}
    </AppShell>
  );
}
