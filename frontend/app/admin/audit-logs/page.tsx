"use client";
/** Read-only audit log browser (filters + full-text search). */
import { useEffect, useState } from "react";
import AppShell from "@/components/AppShell";
import DataTable, { PaginationControls } from "@/components/DataTable";
import { useRequireRole } from "@/lib/auth-context";
import { samsRequest, ApiError } from "@/lib/api";
import { formatThaiDateTime } from "@/lib/format";
import { alertError } from "@/lib/swal";
import type { AuditLog } from "@/lib/types";

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

export default function AdminAuditLogsPage() {
  const user = useRequireRole(["admin"]);
  const [rows, setRows] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [actionInput, setActionInput] = useState("");
  const [action, setAction] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setLoading(true);
      try {
        const params: Record<string, string | number> = { page, page_size: 20 };
        if (action) params.action = action;
        if (search.trim()) params.search = search.trim();
        const { data, envelope } = await samsRequest<AuditLog[]>({ url: "/audit-logs/", params });
        if (cancelled) return;
        setRows(data ?? []);
        setPages(envelope.pagination?.pages ?? 1);
        setCount(envelope.pagination?.count ?? (data?.length ?? 0));
      } catch (error) {
        if (!cancelled) {
          setRows([]);
          await alertError("โหลด Audit Log ไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [page, action, search]);

  return (
    <AppShell title="Audit Log — บันทึกการกระทำทั้งหมด (อ่านอย่างเดียว)">
      {!user && null}
      <div className="mb-4 flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
        <form
          className="flex flex-1 min-w-[220px] items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setAction(actionInput.trim());
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="action" className="text-xs font-medium text-slate-500">
              กรองด้วยชื่อ action
            </label>
            <input
              id="action"
              value={actionInput}
              onChange={(e) => setActionInput(e.target.value)}
              placeholder="เช่น auth_login_success, session_create"
              className={inputClass}
            />
          </div>
          <button type="submit" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">
            กรอง
          </button>
        </form>
        <form
          className="flex flex-1 min-w-[220px] items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(searchInput);
          }}
        >
          <div className="flex flex-1 flex-col gap-1">
            <label htmlFor="audit-search" className="text-xs font-medium text-slate-500">
              ค้นหาทั่วไป
            </label>
            <input
              id="audit-search"
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="username, resource…"
              className={inputClass}
            />
          </div>
          <button type="submit" className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800">
            ค้นหา
          </button>
        </form>
        <button
          type="button"
          onClick={() => {
            setActionInput("");
            setSearchInput("");
            setAction("");
            setSearch("");
            setPage(1);
          }}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
        >
          ล้างตัวกรอง
        </button>
      </div>

      <DataTable<AuditLog>
        columns={[
          { key: "created_at", label: "เวลา", render: (r) => formatThaiDateTime(r.created_at) },
          { key: "actor_username", label: "ผู้กระทำ", render: (r) => r.actor_username || "(system)" },
          { key: "action", label: "การกระทำ", render: (r) => <code className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">{r.action}</code> },
          { key: "resource_type", label: "ประเภททรัพยากร" },
          { key: "resource_id", label: "รหัสทรัพยากร", render: (r) => r.resource_id || "-" },
          {
            key: "metadata",
            label: "รายละเอียด",
            render: (r) =>
              r.metadata && Object.keys(r.metadata).length > 0 ? (
                <code className="block max-w-sm truncate rounded bg-slate-100 px-2 py-0.5 text-xs">
                  {JSON.stringify(r.metadata)}
                </code>
              ) : (
                "-"
              ),
          },
          { key: "ip_address", label: "IP", render: (r) => r.ip_address ?? "-" },
        ]}
        rows={rows}
        loading={loading}
        emptyMessage="ยังไม่มีบันทึก Audit Log ที่ตรงกับตัวกรอง"
      />
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />
    </AppShell>
  );
}
