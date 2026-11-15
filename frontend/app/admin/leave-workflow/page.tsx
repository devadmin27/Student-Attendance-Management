"use client";
/**
 * Admin: configurable approval step order for leave requests.
 *
 * `LeaveWorkflowConfig` decides which roles review a request and in what
 * order. The most specific active scope wins when a request is submitted:
 * กลุ่มเรียน+ภาค > กลุ่มเรียน > หลักสูตร+ภาค > หลักสูตร > ทั้งระบบ.
 * With no active row the default three-step workflow is used, so this page
 * can start empty without breaking submissions.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import AppShell from "@/components/AppShell";
import { StatusBadge } from "@/components/ui";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { loadOptions, type Option } from "@/lib/options";
import { alertError, confirmDialog, toastSuccess } from "@/lib/swal";
import type { LeaveWorkflowConfig, LeaveWorkflowRoleType } from "@/lib/types";

const ROLE_ORDER: { value: LeaveWorkflowRoleType; label: string; hint?: string }[] = [
  { value: "advisor", label: "อาจารย์ที่ปรึกษา" },
  { value: "program_head", label: "หัวหน้าหน่วยหลักสูตร" },
  {
    value: "final_approver",
    label: "ผู้มีอำนาจอนุมัติ",
    hint: "ขั้นสุดท้ายและต้องมีเสมอ",
  },
];

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

interface FormState {
  name: string;
  program: string;
  class_group: string;
  academic_term: string;
  roles: LeaveWorkflowRoleType[];
  is_active: boolean;
}

const EMPTY_FORM: FormState = {
  name: "",
  program: "",
  class_group: "",
  academic_term: "",
  roles: ["advisor", "program_head", "final_approver"],
  is_active: true,
};

function scopeLabel(row: LeaveWorkflowConfig): string {
  const parts: string[] = [];
  parts.push(row.program_name ?? "ทั้งระบบ");
  if (row.class_group_name) parts.push(`กลุ่ม ${row.class_group_name}`);
  if (row.academic_term) parts.push(`ภาค ${row.term_label}`);
  return parts.join(" · ");
}

function buildSteps(roles: LeaveWorkflowRoleType[]): LeaveWorkflowRoleType[] {
  return ROLE_ORDER.map((role) => role.value).filter((role) =>
    roles.includes(role),
  );
}

export default function AdminLeaveWorkflowPage() {
  const user = useRequireRole(["admin"]);
  const [rows, setRows] = useState<LeaveWorkflowConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [options, setOptions] = useState<{
    programs: Option[];
    classGroups: Option[];
    terms: Option[];
  }>({ programs: [], classGroups: [], terms: [] });
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<LeaveWorkflowConfig | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await samsRequest<LeaveWorkflowConfig[]>({
        url: "/leave-workflow-configs/",
        params: { page_size: 100 },
      });
      setRows(data ?? []);
    } catch (error) {
      setRows([]);
      await alertError(
        "โหลดการตั้งค่า Workflow ไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshRef = useRef(refresh);

  useEffect(() => {
    refreshRef.current = refresh;
  });

  useEffect(() => {
    // Load through a ref so this mount-only effect does not cascade renders.
    void refreshRef.current();
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [programs, classGroups, terms] = await Promise.all([
        loadOptions("programs").catch(() => [] as Option[]),
        loadOptions("class-groups").catch(() => [] as Option[]),
        loadOptions("academic-terms").catch(() => [] as Option[]),
      ]);
      if (!cancelled) setOptions({ programs, classGroups, terms });
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const openCreate = () => {
    setEditing(null);
    setForm(EMPTY_FORM);
    setModalOpen(true);
  };

  const openEdit = (row: LeaveWorkflowConfig) => {
    setEditing(row);
    setForm({
      name: row.name,
      program: row.program ?? "",
      class_group: row.class_group ?? "",
      academic_term: row.academic_term ?? "",
      roles:
        row.steps.length > 0
          ? // Keep the canonical order regardless of what the API returned.
            buildSteps(row.steps)
          : ["final_approver"],
      is_active: row.is_active,
    });
    setModalOpen(true);
  };

  const toggleRole = (role: LeaveWorkflowRoleType) => {
    if (role === "final_approver") return; // always required
    setForm((prev) => ({
      ...prev,
      roles: prev.roles.includes(role)
        ? prev.roles.filter((value) => value !== role)
        : [...prev.roles, role],
    }));
  };

  const submit = async () => {
    if (saving) return;
    const steps = buildSteps(form.roles);
    if (!steps.includes("final_approver")) {
      await alertError("ขั้นตอนสุดท้ายต้องเป็นผู้มีอำนาจอนุมัติ");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        program: form.program || null,
        class_group: form.class_group || null,
        academic_term: form.academic_term || null,
        steps,
        is_active: form.is_active,
      };
      if (editing) {
        await samsRequest<LeaveWorkflowConfig>({
          url: `/leave-workflow-configs/${editing.id}/`,
          method: "PATCH",
          data: payload,
        });
        await toastSuccess("อัปเดตชุดขั้นตอน Workflow สำเร็จ");
      } else {
        await samsRequest<LeaveWorkflowConfig>({
          url: "/leave-workflow-configs/",
          method: "POST",
          data: payload,
        });
        await toastSuccess("เพิ่มชุดขั้นตอน Workflow สำเร็จ");
      }
      setModalOpen(false);
      setEditing(null);
      setForm(EMPTY_FORM);
      await refresh();
    } catch (error) {
      await alertError(
        "บันทึกการตั้งค่าไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    } finally {
      setSaving(false);
    }
  };

  const remove = async (row: LeaveWorkflowConfig) => {
    const confirmed = await confirmDialog({
      title: "ยืนยันการลบชุดขั้นตอน",
      text: "คำร้องที่ส่งแล้วจะไม่เปลี่ยน Workflow ย้อนหลัง — การลบมีผลกับคำร้องที่ส่งใหม่เท่านั้น",
      confirmText: "ลบ",
    });
    if (!confirmed) return;
    try {
      await samsRequest({
        url: `/leave-workflow-configs/${row.id}/`,
        method: "DELETE",
      });
      await toastSuccess("ลบชุดขั้นตอน Workflow สำเร็จ");
      await refresh();
    } catch (error) {
      await alertError(
        "ลบไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    }
  };

  const preview = buildSteps(form.roles)
    .map((role) => ROLE_ORDER.find((item) => item.value === role)?.label ?? role)
    .join(" → ");

  return (
    <AppShell title="ตั้งค่าลำดับ Workflow ใบลา">
      {!user && null}
      <div className="mb-4 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-xs text-blue-900">
        <p className="font-medium">ลำดับความเฉพาะเจาะจงของขอบเขต</p>
        <p className="mt-1 text-blue-800">
          กลุ่มเรียน + ภาคการศึกษา &gt; กลุ่มเรียน &gt; หลักสูตร + ภาคการศึกษา &gt;
          หลักสูตร &gt; ทั้งระบบ — หากไม่มีรายการที่เปิดใช้งาน ระบบจะใช้ค่าเริ่มต้น
          อาจารย์ที่ปรึกษา → หัวหน้าหน่วยหลักสูตร → ผู้มีอำนาจอนุมัติ (3 ขั้น)
        </p>
        <p className="mt-1 text-blue-800">
          ขั้นตอนต้องเรียงตามลำดับเดิม ห้ามซ้ำ และต้องลงท้ายด้วยผู้มีอำนาจอนุมัติ
          — ผู้รับผิดชอบแต่ละบทบาทตั้งได้ที่หน้า “ผู้รับผิดชอบ Workflow ใบลา”
        </p>
      </div>

      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-800">
          ชุดขั้นตอนที่กำหนดไว้
        </h2>
        <button
          type="button"
          onClick={openCreate}
          className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
        >
          + เพิ่มชุดขั้นตอน
        </button>
      </div>

      {loading ? (
        <p className="animate-pulse text-slate-500">กำลังโหลด…</p>
      ) : rows.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-6 text-center text-sm text-slate-500">
          ยังไม่มีการตั้งค่า — ระบบจะใช้ Workflow เริ่มต้น 3 ขั้น
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 font-medium">ชื่อชุดขั้นตอน</th>
                <th className="px-4 py-3 font-medium">ขอบเขต</th>
                <th className="px-4 py-3 font-medium">ลำดับขั้นตอน</th>
                <th className="px-4 py-3 font-medium">สถานะ</th>
                <th className="px-4 py-3 text-right font-medium">จัดการ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <tr key={row.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 text-slate-800">
                    {row.name || "—"}
                  </td>
                  <td className="px-4 py-3 text-slate-600">{scopeLabel(row)}</td>
                  <td className="px-4 py-3 text-slate-700">
                    <div>{row.steps_display}</div>
                    <div className="text-xs text-slate-400">
                      {row.step_count} ขั้น
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge
                      status={row.is_active ? "active" : "inactive"}
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end gap-2">
                      <button
                        type="button"
                        onClick={() => openEdit(row)}
                        className="rounded-lg border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-100"
                      >
                        แก้ไข
                      </button>
                      <button
                        type="button"
                        onClick={() => void remove(row)}
                        className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
                      >
                        ลบ
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-slate-900/50"
            onClick={() => !saving && setModalOpen(false)}
          />
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void submit();
            }}
            className="relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="mb-4 text-lg font-semibold text-slate-900">
              {editing ? "แก้ไขชุดขั้นตอน Workflow" : "เพิ่มชุดขั้นตอน Workflow"}
            </h2>
            <div className="space-y-3">
              <div className="flex flex-col gap-1">
                <label htmlFor="wf-name" className="text-sm font-medium text-slate-700">
                  ชื่อชุดขั้นตอน (ไม่บังคับ)
                </label>
                <input
                  id="wf-name"
                  type="text"
                  value={form.name}
                  onChange={(event) =>
                    setForm((prev) => ({ ...prev, name: event.target.value }))
                  }
                  placeholder="เช่น หลักสูตร 2 ขั้น"
                  className={inputClass}
                />
              </div>

              <div className="flex flex-col gap-1">
                <label htmlFor="wf-steps" className="text-sm font-medium text-slate-700">
                  ขั้นตอนการพิจารณา
                </label>
                <div
                  id="wf-steps"
                  className="space-y-1 rounded-lg border border-slate-200 bg-white p-2"
                >
                  {ROLE_ORDER.map((role) => {
                    const checked = form.roles.includes(role.value);
                    const locked = role.value === "final_approver";
                    return (
                      <label
                        key={role.value}
                        className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-blue-50"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          disabled={locked}
                          onChange={() => toggleRole(role.value)}
                          className="h-4 w-4 rounded border-slate-300"
                        />
                        <span>{role.label}</span>
                        {role.hint && (
                          <span className="text-xs text-slate-400">
                            ({role.hint})
                          </span>
                        )}
                      </label>
                    );
                  })}
                </div>
                <span className="text-xs text-slate-500">
                  ลำดับที่จะบันทึก: {preview || "—"}
                </span>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div className="flex flex-col gap-1">
                  <label htmlFor="wf-program" className="text-sm font-medium text-slate-700">
                    หลักสูตร (ขอบเขต)
                  </label>
                  <select
                    id="wf-program"
                    value={form.program}
                    onChange={(event) =>
                      setForm((prev) => ({ ...prev, program: event.target.value }))
                    }
                    className={inputClass}
                  >
                    <option value="">ทั้งระบบ</option>
                    {options.programs.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label
                    htmlFor="wf-class-group"
                    className="text-sm font-medium text-slate-700"
                  >
                    กลุ่มเรียน (ถ้าเฉพาะกลุ่ม)
                  </label>
                  <select
                    id="wf-class-group"
                    value={form.class_group}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        class_group: event.target.value,
                      }))
                    }
                    className={inputClass}
                  >
                    <option value="">ทุกกลุ่ม</option>
                    {options.classGroups.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1">
                  <label
                    htmlFor="wf-term"
                    className="text-sm font-medium text-slate-700"
                  >
                    ภาคการศึกษา (ถ้าเฉพาะภาค)
                  </label>
                  <select
                    id="wf-term"
                    value={form.academic_term}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        academic_term: event.target.value,
                      }))
                    }
                    className={inputClass}
                  >
                    <option value="">ทุกภาคเรียน</option>
                    {options.terms.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-2 self-end pb-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(event) =>
                      setForm((prev) => ({
                        ...prev,
                        is_active: event.target.checked,
                      }))
                    }
                    className="h-4 w-4 rounded border-slate-300"
                  />
                  เปิดใช้งาน
                </label>
              </div>
            </div>

            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                disabled={saving}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                ยกเลิก
              </button>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800 disabled:opacity-50"
              >
                {saving ? "กำลังบันทึก…" : "บันทึก"}
              </button>
            </div>
          </form>
        </div>
      )}
    </AppShell>
  );
}
