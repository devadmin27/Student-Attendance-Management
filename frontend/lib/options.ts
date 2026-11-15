/**
 * Option loaders for <select> fields (FK pickers).
 * Page-size-capped paginated fetches; used by CrudPage and report filters.
 * `filterRow` (optional) narrows rows after fetching, e.g. only offerings
 * that are still open so users cannot attach new data to closed courses.
 */
import { samsRequest } from "@/lib/api";

export interface Option {
  label: string;
  value: string;
}

type MetaOptionData = { results?: Record<string, unknown>[] };

async function fetchAllPages(
  basePath: string,
  labelKeys: string[],
  valueKey = "id",
  filterRow?: (row: Record<string, unknown>) => boolean,
  params: Record<string, string | number> = {},
): Promise<Option[]> {
  const out: Option[] = [];
  let page = 1;
  for (;;) {
    const { data, envelope } = await samsRequest<MetaOptionData>({
      url: basePath,
      params: { ...params, page, page_size: 100 },
    });
    const rows = data.results ?? (Array.isArray(data) ? (data as unknown as Record<string, unknown>[]) : []);
    for (const row of rows) {
      if (filterRow && !filterRow(row)) continue;
      const label = labelKeys
        .map((k) => row[k])
        .filter((v) => v !== undefined && v !== null && String(v).trim() !== "")
        .join(" · ");
      out.push({ label: label || String(row[valueKey] ?? ""), value: String(row[valueKey]) });
    }
    const pages = envelope.pagination?.pages ?? 1;
    if (pages > page && rows.length > 0) {
      page += 1;
    } else {
      break;
    }
  }
  return out;
}

export type OptionsKey =
  | "programs"
  | "class-groups"
  | "academic-terms"
  | "courses"
  | "course-offerings"
  | "course-offerings-active" // เฉพาะ offering ที่ยังไม่จบภาคเรียน/ยกเลิก
  | "instructors"
  | "students"
  | "users" // อาจารย์และผู้ดูแลระบบ (สำหรับผู้รับผิดชอบ Workflow)
  | "enrollments"
  | "schedules";

const OPEN_OFFERING_STATUSES = new Set(["open", "in_progress"]);

/** Label สำหรับ dropdown รายวิชาที่เปิดสอน: รหัสวิชา · ชื่อรายวิชา */
function offeringOptions(options: { activeOnly: boolean }): Promise<Option[]> {
  return fetchAllPages("/course-offerings/", ["course_code", "course_name"], "id", (row) =>
    options.activeOnly ? OPEN_OFFERING_STATUSES.has(String(row.status ?? "")) : true,
  );
}

export async function loadOptions(key: OptionsKey): Promise<Option[]> {
  switch (key) {
    case "programs":
      return fetchAllPages("/programs/", ["program_code", "program_name"]);
    case "class-groups":
      return fetchAllPages("/class-groups/", ["group_code", "group_name"]);
    case "academic-terms":
      return fetchAllPages("/academic-terms/", ["academic_year", "semester", "semester_display"]);
    case "courses":
      return fetchAllPages("/courses/", ["course_code", "course_name"]);
    case "course-offerings":
    case "course-offerings-active":
      return offeringOptions({ activeOnly: key === "course-offerings-active" });
    case "instructors":
      return fetchAllPages("/instructors/", ["employee_code", "first_name", "last_name"]);
    case "students":
      return fetchAllPages("/students/", ["student_code", "first_name", "last_name"]);
    case "users":
      return loadUserOptions();
    default:
      return [];
  }
}

/**
 * Option loader for approval workflow assignees (Phase 2).
 * The endpoint is admin-only; advisors/heads must be instructors while the
 * final approver may also be an admin account.
 */
export async function loadUserOptions(
  roles: Array<"instructor" | "admin"> = ["instructor", "admin"],
): Promise<Option[]> {
  const groups = await Promise.all(
    roles.map((role) =>
      fetchAllPages("/users/", ["display_name", "username"], "id", undefined, {
        role,
        is_active: "true",
      }),
    ),
  );
  const seen = new Set<string>();
  return groups
    .flat()
    .filter((option) => {
      if (seen.has(option.value)) return false;
      seen.add(option.value);
      return true;
    })
    .sort((a, b) => a.label.localeCompare(b.label, "th"));
}
