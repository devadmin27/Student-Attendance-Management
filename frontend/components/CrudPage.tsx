"use client";
/**
 * Generic admin CRUD page (list + create/edit modal + delete).
 * Backed by the SAMS envelope API with server-side pagination/search.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DataTable, { PaginationControls, type ColumnDef } from "@/components/DataTable";
import { samsRequest, ApiError } from "@/lib/api";
import { confirmDialog, toastSuccess } from "@/lib/swal";
import { loadOptions, type Option, type OptionsKey } from "@/lib/options";
import { alertError } from "@/lib/swal";

export type FieldType =
  | "text"
  | "email"
  | "number"
  | "password"
  | "textarea"
  | "date"
  | "time"
  | "datetime-local"
  | "checkbox"
  | "select"
  | "select-search" // FK picker with free-text filter (ค้นหาด้วยรหัสวิชา)
  | "multiselect"; // many FKs (อาจารย์ผู้รับผิดชอบหลายคน)

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  options?: Option[];
  optionsKey?: OptionsKey; // async FK options
  required?: boolean;
  createOnly?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: string;
  defaultValue?: string | number | boolean;
  hint?: string;
}

export interface FilterDef {
  name: string;
  label: string;
  optionsKey?: OptionsKey;
  options?: Option[];
}

const inputClass =
  "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100";

const isUuid = (v: string) => /^[0-9a-f]{8}-[0-9a-f]{4}/i.test(v);

/**
 * Autocomplete select (select-search fields: รายวิชา, นักศึกษา, กลุ่มเรียน, …).
 * - List appears as a dropdown directly BELOW the input (top-full), never
 *   covering the field itself.
 * - Only options matching the typed text (code or label, case-insensitive)
 *   are shown.
 * - Keyboard: ↓/↑ move the highlight, Enter picks the highlighted option
 *   (and does NOT submit the form while open), Escape closes, Tab moves on.
 * - Mouse: click picks; hovering updates the highlight.
 * This component backs every CrudPage using type:"select-search".
 */
function SelectSearchField({
  name,
  label,
  required,
  placeholder,
  options,
  value,
  text,
  onTextChange,
  onSelect,
}: {
  name: string;
  label: string;
  required?: boolean;
  placeholder?: string;
  options: Option[];
  value: string;
  text: string;
  onTextChange: (t: string) => void; // set __text (clears id when no longer matching)
  onSelect: (id: string, label: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const listRef = useRef<HTMLDivElement | null>(null);

  const needle = text.trim().toLowerCase();
  // FK options carry UUID values — searching a UUID substring (e.g. "22" inside
  // a generated id) would surface unrelated subjects. Match the visible label
  // always; match the raw value only when it is not a UUID (plain-code options).
  const filtered = useMemo(
    () =>
      needle
        ? options
            .filter(
              (o) =>
                o.label.toLowerCase().includes(needle) ||
                (!isUuid(o.value) && o.value.toLowerCase().includes(needle)),
            )
            .slice(0, 30)
        : [],
    [needle, options],
  );

  // New search text starts highlight back at the first match.
  useEffect(() => {
    setActive(0);
  }, [needle]);

  // Keep the highlighted option visible while moving with the keyboard.
  useEffect(() => {
    if (!open) return;
    listRef.current
      ?.querySelector<HTMLElement>(`[data-idx="${active}"]`)
      ?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const pick = (o: Option) => {
    onSelect(o.value, o.label);
    setOpen(false);
  };

  const onKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (filtered.length === 0) return;
      if (!open) {
        setOpen(true);
        return;
      }
      setActive((i) => Math.min(i + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open || filtered.length === 0) return;
      setActive((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      // Open + something highlighted → pick it and suppress the form submit.
      // Closed → fall through so the form submits normally.
      if (open && filtered[active]) {
        event.preventDefault();
        pick(filtered[active]);
      }
    } else if (event.key === "Escape") {
      if (open) {
        event.preventDefault();
        setOpen(false);
      }
    }
  };

  return (
    <div className="flex flex-col gap-1">
      <label htmlFor={name} className="text-sm font-medium text-slate-700">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </label>
      <input type="hidden" name={name} id={`field-${name}`} required={required} value={value} readOnly />
      <div className="relative">
        <input
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={`list-${name}`}
          aria-autocomplete="list"
          autoComplete="off"
          placeholder={placeholder ?? "พิมพ์เพื่อค้นหา…"}
          value={text}
          onChange={(event) => {
            onTextChange(event.target.value);
            setOpen(true);
          }}
          onFocus={() => {
            if (needle) setOpen(true);
          }}
          onBlur={() => setOpen(false)}
          onKeyDown={onKeyDown}
          className={inputClass}
        />
        {open && (
          <div
            id={`list-${name}`}
            ref={listRef}
            role="listbox"
            className="absolute left-0 right-0 top-full z-30 mt-1 max-h-56 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-lg"
          >
            {filtered.length === 0 && (
              <div className="px-3 py-2 text-sm text-slate-400">ไม่พบรายการที่ค้นหา</div>
            )}
            {filtered.map((o, i) => (
              <button
                key={o.value}
                type="button"
                role="option"
                aria-selected={value === o.value}
                data-idx={i}
                // keep focus (and the open state) so the blur-based close
                // never fires before the click registers
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setActive(i)}
                onClick={() => pick(o)}
                className={`block w-full px-3 py-2 text-left text-sm ${
                  i === active ? "bg-blue-100 text-blue-900" : ""
                } ${value === o.value ? "font-medium underline decoration-blue-400 underline-offset-2" : ""}`}
              >
                {o.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CrudPage<T extends { id: string }>({
  // `title` remains a valid prop declared in the signature below; it is only
  // used for documentation/typing, the page renders its own AppShell heading.
  basePath,
  fields,
  columns,
  searchPlaceholder = "ค้นหา…",
  filters = [],
  rowActions,
  createTitle = "เพิ่มรายการใหม่",
  createValue,
  updateValue,
  deleteLabel = "ลบ",
  canEdit = true,
  canDelete = true,
  emptyMessage = "ยังไม่มีข้อมูล",
  transformRow,
  headerExtra,
}: {
  title: string;
  basePath: string;
  fields: FieldDef[];
  columns: ColumnDef<T>[];
  searchPlaceholder?: string;
  filters?: FilterDef[];
  rowActions?: (row: T, refresh: () => void) => React.ReactNode; // custom (non-crud) actions
  headerExtra?: (refresh: () => void) => React.ReactNode; // extra toolbar action (gets refresh)
  createTitle?: string;
  /** Map the modal form into a create payload (e.g. split into nested objects). */
  createValue?: (values: Record<string, unknown>) => Record<string, unknown>;
  updateValue?: (values: Record<string, unknown>) => Record<string, unknown>;
  deleteLabel?: string;
  canEdit?: boolean;
  canDelete?: boolean;
  emptyMessage?: string;
  transformRow?: (row: T) => T;
}) {
  const [rows, setRows] = useState<T[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [count, setCount] = useState(0);
  const [search, setSearch] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [filterValues, setFilterValues] = useState<Record<string, string>>({});
  const [filterOptions, setFilterOptions] = useState<Record<string, Option[]>>({});
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [fkOptions, setFkOptions] = useState<Record<string, Option[]>>({});
  const [saving, setSaving] = useState(false);

  const listFields = useMemo(() => fields, [fields]);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = { page, page_size: 20 };
      if (search.trim()) params.search = search.trim();
      for (const [key, value] of Object.entries(filterValues)) {
        if (value) params[key] = value;
      }
      const { data, envelope } = await samsRequest<T[]>({ url: basePath, params });
      let list = data ?? [];
      if (transformRow) list = list.map(transformRow);
      setRows(list);
      setPages(envelope.pagination?.pages ?? 1);
      setCount(envelope.pagination?.count ?? list.length);
    } catch (error) {
      setRows([]);
      await alertError("โหลดรายการไม่สำเร็จ", error instanceof ApiError ? error.message : undefined);
    } finally {
      setLoading(false);
    }
  }, [basePath, page, search, filterValues, transformRow]);

  const refreshRef = useRef(refresh);

  useEffect(() => {
    refreshRef.current = refresh;
  });
  // Trigger list fetch on query signature change only (not on callback identity).
  const filterSig = JSON.stringify(filterValues);
  useEffect(() => {
    void refreshRef.current();
  }, [basePath, page, search, filterSig]);

  // Load select options once per unique options-key set (both modal FK selects and page filters).
  const optionsSig = useMemo(() => {
    const keys = new Set<string>();
    for (const f of listFields) {
      if (f.optionsKey && !f.options && f.type !== "text") keys.add(f.optionsKey);
    }
    for (const f of filters) {
      if (f.optionsKey && !f.options) keys.add(f.optionsKey);
    }
    return Array.from(keys).sort().join(",");
  }, [listFields, filters]);
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const modalKeys = listFields
        .filter((f) => f.optionsKey && !f.options && f.type !== "text")
        .map((f) => f.optionsKey as OptionsKey);
      const filterKeys = filters
        .filter((f) => f.optionsKey && !f.options)
        .map((f) => f.optionsKey as OptionsKey);
      const toFetch = Array.from(new Set<OptionsKey>([...modalKeys, ...filterKeys]));
      const results = await Promise.all(
        toFetch.map(async (key) => [key, await loadOptions(key).catch(() => [] as Option[])] as const),
      );
      if (cancelled) return;
      const map: Record<string, Option[]> = {};
      for (const [key, options] of results) map[key] = options.filter((o) => o.value !== "");
      setFkOptions(map);
      setFilterOptions(map);
    };
    void load();
    return () => {
      cancelled = true;
    };
    // optionsSig is a stable signature derived from filters/listFields;
    // re-subscribing on the raw arrays (new identity each render) would loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [optionsSig]);

  const optionsFor = (field: { options?: Option[]; optionsKey?: OptionsKey }): Option[] =>
    field.options ?? (field.optionsKey ? fkOptions[field.optionsKey] ?? [] : []);

  const openCreate = () => {
    const initial: Record<string, unknown> = {};
    for (const f of listFields) {
      initial[f.name] =
        f.type === "multiselect"
          ? Array.isArray(f.defaultValue)
            ? f.defaultValue
            : []
          : f.defaultValue ?? (f.type === "checkbox" ? true : "");
    }
    setForm(initial);
    setEditing(null);
    setModalOpen(true);
  };

  const openEdit = (row: T) => {
    const initial: Record<string, unknown> = {};
    for (const f of listFields) {
      if (f.createOnly) {
        initial[f.name] =
          f.type === "multiselect" ? [] : f.defaultValue ?? (f.type === "checkbox" ? true : "");
        continue;
      }
      const raw = (row as unknown as Record<string, unknown>)[f.name] ?? "";
      if (f.type === "multiselect") {
        initial[f.name] = Array.isArray(raw)
          ? raw.map((x: unknown) =>
              x && typeof x === "object" ? String((x as { id?: unknown }).id) : String(x),
            )
          : [];
      } else if (f.type === "select-search") {
        const id = String(raw ?? "");
        const opt = optionsFor(f).find((o) => o.value === id);
        initial[f.name] = id;
        initial[`${f.name}__text`] = opt ? opt.label : id;
      } else {
        initial[f.name] = f.type === "checkbox" ? Boolean(raw) : String(raw ?? "");
      }
    }
    setForm(initial);
    setEditing(row);
    setModalOpen(true);
  };

  /** Serialize one form value to its API representation. */
  const serializeValue = (f: FieldDef, raw: unknown): unknown => {
    if (f.type === "checkbox") return Boolean(raw);
    if (f.type === "multiselect")
      return Array.isArray(raw) ? raw.map((x) => String(x)) : [];
    const text = String(raw ?? "").trim();
    if (text === "") return null;
    if (f.type === "number") return Number(text);
    if (f.type === "datetime-local") {
      // Force +07:00 offset so Django stores the correct Asia/Bangkok instant.
      const iso = text.length === 16 ? `${text}:00` : text;
      return `${iso}+07:00`;
    }
    return text;
  };

  const buildPayload = (mode: "create" | "update"): Record<string, unknown> => {
    const payload: Record<string, unknown> = {};
    for (const f of listFields) {
      // createOnly fields (e.g. passwords) are sent on create, skipped on update.
      if (f.createOnly && mode === "update") continue;
      const raw = form[f.name];
      const value = serializeValue(f, raw);
      // Skip optional empty values (null) in both modes — sending null to a
      // non-nullable serializer field turns an empty form into a 400.
      if (value === null && !(f.required ?? false)) continue;
      if (mode === "update" && f.type === "select" && value === null) {
        // PATCH null for nullable FK fields must still be sent when touched.
        payload[f.name] = null;
        continue;
      }
      payload[f.name] = value;
    }
    return payload;
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      const mode = editing ? "update" : "create";
      let payload = buildPayload(mode);
      // select-search stores the picked id in a hidden input the browser
      // skips during native validation — enforce required here instead.
      for (const f of listFields) {
        if (f.type === "select-search" && f.required && !payload[f.name]) {
          setSaving(false); // re-raise as form UI error
          await alertError(`กรุณาเลือก${f.label}`);
          return;
        }
      }
      if (mode === "create" && createValue) payload = createValue(payload);
      if (mode === "update" && updateValue) payload = updateValue(payload);
      await samsRequest({
        url: editing ? `${basePath}${editing.id}/` : `${basePath}`,
        method: editing ? "PATCH" : "POST",
        data: payload,
      });
      setModalOpen(false);
      await toastSuccess(editing ? "แก้ไขข้อมูลสำเร็จ" : "เพิ่มข้อมูลสำเร็จ");
      await refresh();
    } catch (error) {
      if (error instanceof ApiError) {
        await alertError(error.message);
      } else {
        await alertError("บันทึกข้อมูลไม่สำเร็จ");
      }
    } finally {
      setSaving(false);
    }
  };

  const doDelete = async (row: T) => {
    const confirmed = await confirmDialog({
      title: "ยืนยันการลบข้อมูล",
      text: deleteLabel && deleteLabel !== "ลบ" ? deleteLabel : "รายการนี้จะถูกลบแบบถาวรถ้าไม่มีข้อมูลผูกอยู่",
      confirmText: deleteLabel,
    });
    if (!confirmed) return;
    try {
      await samsRequest({ url: `${basePath}${row.id}/`, method: "DELETE" });
      await toastSuccess("ลบข้อมูลสำเร็จ (หากผูกข้อมูลอยู่ระบบจะปิดใช้งานแทน)");
      await refresh();
    } catch (error) {
      await alertError(
        "ลบข้อมูลไม่สำเร็จ",
        error instanceof ApiError ? error.message : undefined,
      );
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <form
          className="flex flex-1 min-w-[240px] gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            setPage(1);
            setSearch(searchInput);
          }}
        >
          <input
            type="search"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder={searchPlaceholder}
            className={`${inputClass} max-w-xs`}
          />
          <button
            type="submit"
            className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-800"
          >
            ค้นหา
          </button>
        </form>
        <button
          type="button"
          onClick={openCreate}
          className="ml-auto rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700"
        >
          ＋ {createTitle}
        </button>
        {headerExtra?.(refresh)}
      </div>

      {filters.length > 0 && (
        <div className="flex flex-wrap items-end gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          {filters.map((f) => (
            <div key={f.name} className="flex flex-col gap-1">
              <label className="text-xs font-medium text-slate-500">{f.label}</label>
              <select
                value={filterValues[f.name] ?? ""}
                onChange={(e) => {
                  setPage(1);
                  setFilterValues((prev) => ({ ...prev, [f.name]: e.target.value }));
                }}
                className={`${inputClass} min-w-[180px]`}
              >
                <option value="">ทั้งหมด</option>
                {(f.options ?? filterOptions[f.optionsKey!] ?? []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </div>
          ))}
          <button
            type="button"
            onClick={() => {
              setFilterValues({});
              setSearchInput("");
              setSearch("");
              setPage(1);
            }}
            className="mb-0.5 rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-600 hover:bg-slate-50"
          >
            ล้างตัวกรอง
          </button>
        </div>
      )}

      <DataTable<T>
        columns={columns}
        rows={rows}
        loading={loading}
        emptyMessage={emptyMessage}
        renderActions={(row) => (
          <>
            {rowActions?.(row, refresh)}
            {canEdit && (
              <button
                type="button"
                onClick={() => openEdit(row)}
                className="rounded-lg border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-100"
              >
                แก้ไข
              </button>
            )}
            {canDelete && (
              <button
                type="button"
                onClick={() => void doDelete(row)}
                className="rounded-lg border border-red-200 bg-red-50 px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-100"
              >
                ลบ
              </button>
            )}
          </>
        )}
      />
      <PaginationControls page={page} pages={pages} count={count} onChange={setPage} />

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => !saving && setModalOpen(false)} />
          <form
            onSubmit={(e) => void submit(e)}
            className="relative z-10 max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-2xl bg-white p-5 shadow-xl"
          >
            <h2 className="mb-4 text-lg font-semibold text-slate-900">
              {editing ? "แก้ไขข้อมูล" : createTitle}
            </h2>
            <div className="space-y-3">
              {listFields
                .filter((f) => !f.createOnly || !editing)
                .map((f) => {
                  const options = optionsFor(f);
                  if (f.type === "select-search") {
                    return (
                      <SelectSearchField
                        key={f.name}
                        name={f.name}
                        label={f.label}
                        required={f.required}
                        placeholder={f.placeholder}
                        options={options}
                        value={String(form[f.name] ?? "")}
                        text={String(form[`${f.name}__text`] ?? "")}
                        onTextChange={(text) =>
                          setForm((p) => {
                            const clean = { ...p, [`${f.name}__text`]: text };
                            // ตัด id ออกทันทีที่ข้อความไม่ตรงกับตัวเลือกที่ถืออยู่
                            const opt = options.find((o) => o.value === p[f.name]);
                            if (!opt || opt.label !== text) clean[f.name] = "";
                            return clean;
                          })
                        }
                        onSelect={(id, label) =>
                          setForm((p) => ({ ...p, [f.name]: id, [`${f.name}__text`]: label }))
                        }
                      />
                    );
                  }
                  if (f.type === "multiselect") {
                    const selected = Array.isArray(form[f.name]) ? (form[f.name] as string[]) : [];
                    return (
                      <div key={f.name} className="flex flex-col gap-1">
                        <label htmlFor={`field-${f.name}`} className="text-sm font-medium text-slate-700">
                          {f.label}
                          {f.required && <span className="text-red-500"> *</span>}
                        </label>
                        <div
                          id={`field-${f.name}`}
                          className="max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2"
                        >
                          {options.length === 0 && (
                            <div className="px-1 py-1 text-sm text-slate-400">ไม่มีตัวเลือก</div>
                          )}
                          {options.map((o) => (
                            <label
                              key={o.value}
                              className="flex cursor-pointer items-center gap-2 rounded px-1 py-1 text-sm hover:bg-blue-50"
                            >
                              <input
                                type="checkbox"
                                checked={selected.includes(o.value)}
                                onChange={(e) => {
                                  const next = e.target.checked
                                    ? [...selected, o.value]
                                    : selected.filter((v) => v !== o.value);
                                  setForm((p) => ({ ...p, [f.name]: next }));
                                }}
                                className="h-4 w-4 rounded border-slate-300"
                              />
                              {o.label}
                            </label>
                          ))}
                        </div>
                        {f.hint && <span className="text-xs text-slate-400">{f.hint}</span>}
                      </div>
                    );
                  }
                  return (
                    <div key={f.name} className="flex flex-col gap-1">
                      <label htmlFor={`field-${f.name}`} className="text-sm font-medium text-slate-700">
                        {f.label}
                        {f.required && <span className="text-red-500"> *</span>}
                      </label>
                      {f.type === "textarea" ? (
                        <textarea
                          id={`field-${f.name}`}
                          required={f.required}
                          rows={3}
                          value={String(form[f.name] ?? "")}
                          onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                          className={inputClass}
                          placeholder={f.placeholder}
                        />
                      ) : f.type === "checkbox" ? (
                        <label className="flex items-center gap-2 text-sm text-slate-700">
                          <input
                            id={`field-${f.name}`}
                            type="checkbox"
                            checked={Boolean(form[f.name])}
                            onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.checked }))}
                            className="h-4 w-4 rounded border-slate-300"
                          />
                          {f.hint ?? "เปิดใช้งาน"}
                        </label>
                      ) : f.type === "select" ? (
                        <select
                          id={`field-${f.name}`}
                          required={f.required}
                          value={String(form[f.name] ?? "")}
                          onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                          className={inputClass}
                        >
                          <option value="">— เลือก —</option>
                          {options.map((o) => (
                            <option key={o.value} value={o.value}>
                              {o.label}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id={`field-${f.name}`}
                          type={f.type}
                          required={f.required}
                          min={f.min}
                          max={f.max}
                          step={f.step}
                          placeholder={f.placeholder}
                          value={String(form[f.name] ?? "")}
                          onChange={(e) => setForm((p) => ({ ...p, [f.name]: e.target.value }))}
                          className={inputClass}
                        />
                      )}
                    </div>
                  );
                })}
            </div>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setModalOpen(false)}
                disabled={saving}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
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
    </div>
  );
}
