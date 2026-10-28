/**
 * Option loaders for <select> fields (FK pickers).
 * Page-size-capped paginated fetches; used by CrudPage and report filters.
 */
import { samsRequest } from "@/lib/api";

export interface Option {
  label: string;
  value: string;
}

type MetaOptionData = { results?: Record<string, unknown>[] };

async function fetchAllPages(basePath: string, labelKeys: string[], valueKey = "id"): Promise<Option[]> {
  const out: Option[] = [];
  let page = 1;
  for (;;) {
    const { data, envelope } = await samsRequest<MetaOptionData>({
      url: basePath,
      params: { page, page_size: 100 },
    });
    const rows = data.results ?? (Array.isArray(data) ? (data as unknown as Record<string, unknown>[]) : []);
    for (const row of rows) {
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
  | "instructors"
  | "students"
  | "enrollments"
  | "schedules";

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
      return fetchAllPages("/course-offerings/", ["course_code", "term_label"]);
    case "instructors":
      return fetchAllPages("/instructors/", ["employee_code", "first_name", "last_name"]);
    case "students":
      return fetchAllPages("/students/", ["student_code", "first_name", "last_name"]);
    default:
      return [];
  }
}
