"use client";
/** Generic data table used by every list page. */
export interface ColumnDef<T> {
  key: string;
  label: string;
  render?: (row: T) => React.ReactNode;
  className?: string;
}

export default function DataTable<T extends { id: string }>({
  columns,
  rows,
  loading,
  emptyMessage = "ยังไม่มีข้อมูล",
  renderActions,
}: {
  columns: ColumnDef<T>[];
  rows: T[];
  loading?: boolean;
  emptyMessage?: string;
  renderActions?: (row: T) => React.ReactNode;
}) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            {columns.map((col) => (
              <th key={col.key} className={`px-4 py-3 font-medium ${col.className ?? ""}`}>
                {col.label}
              </th>
            ))}
            {renderActions && <th className="px-4 py-3 text-right font-medium">การจัดการ</th>}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length + (renderActions ? 1 : 0)} className="px-4 py-10 text-center text-slate-500">
                <span className="inline-block animate-pulse">กำลังโหลดข้อมูล…</span>
              </td>
            </tr>
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length + (renderActions ? 1 : 0)} className="px-4 py-10 text-center text-slate-500">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={row.id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50/60">
                {columns.map((col) => (
                  <td key={col.key} className={`px-4 py-3 align-top ${col.className ?? ""}`}>
                    {col.render ? col.render(row) : String((row as Record<string, unknown>)[col.key] ?? "-")}
                  </td>
                ))}
                {renderActions && (
                  <td className="px-4 py-3 text-right align-top">
                    <div className="flex flex-wrap items-center justify-end gap-1.5">{renderActions(row)}</div>
                  </td>
                )}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

export function PaginationControls({
  page,
  pages,
  count,
  onChange,
}: {
  page: number;
  pages: number;
  count?: number;
  onChange: (nextPage: number) => void;
}) {
  if (pages <= 1) {
    return count !== undefined ? (
      <div className="mt-2 text-xs text-slate-500">ทั้งหมด {count} รายการ</div>
    ) : null;
  }
  return (
    <div className="mt-3 flex items-center justify-between text-sm">
      <span className="text-xs text-slate-500">
        หน้า {page} / {pages}
        {count !== undefined ? ` (${count} รายการ)` : ""}
      </span>
      <div className="flex gap-2">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
        >
          ก่อนหน้า
        </button>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
          className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-700 disabled:cursor-not-allowed disabled:opacity-40 hover:bg-slate-50"
        >
          ถัดไป
        </button>
      </div>
    </div>
  );
}
