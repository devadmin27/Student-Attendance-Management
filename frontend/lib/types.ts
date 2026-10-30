/** Shared API resource types (mirrors backend serializers). */

export type Role = "admin" | "instructor" | "student";
export type AttendanceStatus = "present" | "late" | "absent" | "excused";

export interface User {
  id: string;
  username: string;
  email: string;
  role: Role;
  is_active: boolean;
  date_joined?: string;
  created_at?: string;
  updated_at?: string;
  student_code?: string | null;
}

export interface StudentProfile {
  id: string;
  user: string;
  username: string;
  email: string;
  account_active: boolean;
  student_code: string;
  first_name: string;
  last_name: string;
  program: string | null;
  program_name: string | null;
  academic_year_level: number;
  class_group: string | null;
  class_group_name: string | null;
  status: "active" | "suspended" | "inactive";
  created_at?: string;
  updated_at?: string;
}

export interface InstructorProfile {
  id: string;
  user: string;
  username: string;
  email: string;
  employee_code: string;
  first_name: string;
  last_name: string;
  department: string;
  status: "active" | "suspended" | "inactive";
  created_at?: string;
  updated_at?: string;
}

export interface Program {
  id: string;
  program_code: string;
  program_name: string;
  degree_level: "bachelor" | "master" | "doctoral";
  is_active: boolean;
}

export interface ClassGroup {
  id: string;
  group_code: string;
  group_name: string;
  program: string;
  program_name: string;
  academic_year_level: number;
}

export interface AcademicTerm {
  id: string;
  academic_year: number;
  semester: "1" | "2" | "3";
  semester_display: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  is_current: boolean;
}

export interface Course {
  id: string;
  course_code: string;
  course_name: string;
  credits: string;
  description: string;
  is_active: boolean;
}

export interface CourseOffering {
  id: string;
  course: string;
  course_code: string;
  course_name: string;
  academic_term: string;
  term_label: string;
  instructor: string | null;
  instructor_name: string | null;
  /** รายการ pk ของอาจารย์ผู้รับผิดชอบทั้งหมด (เลือกได้หลายคน) */
  instructors: string[];
  instructor_ids?: string[];
  instructor_names?: string[];
  class_group: string | null;
  status: "open" | "in_progress" | "completed" | "cancelled";
  enrollment_count: number;
}

export interface Enrollment {
  id: string;
  student: string;
  student_code: string;
  student_name: string;
  course_offering: string;
  course_code: string;
  course_name: string;
  enrollment_status: "enrolled" | "dropped" | "completed";
  enrolled_at: string;
}

export interface ClassSchedule {
  id: string;
  course_offering: string;
  course_code: string;
  course_name: string;
  term_label: string;
  weekday: number;
  weekday_display: string;
  start_time: string;
  end_time: string;
  classroom: string;
  status: "planned" | "active" | "cancelled";
}

export interface AttendanceSession {
  id: string;
  course_offering: string;
  course_code: string;
  course_name: string;
  term_label: string;
  class_schedule: string | null;
  instructor: string;
  instructor_name: string | null;
  session_date: string;
  check_in_start: string;
  check_in_end: string;
  late_threshold_minutes: number;
  status: "scheduled" | "open" | "paused" | "closed" | "cancelled";
  status_display: string;
  enrolled_count: number;
  checked_in_count: number;
  created_at?: string;
  updated_at?: string;
  closed_at?: string | null;
}

export interface QRTokenInfo {
  id: string;
  expires_at: string;
  expires_in_seconds: number;
  issued_at: string;
  use_count: number;
  qr: string; // raw token — shown once per issue
}

export interface RosterRow {
  id: string;
  student_code: string;
  student_name: string;
  checked_in_status: AttendanceStatus | null;
  checked_in_at: string | null;
}

export interface AttendanceRecord {
  id: string;
  attendance_session: string;
  session_date: string;
  course_code: string;
  student: string;
  student_code: string;
  student_name: string;
  status: AttendanceStatus;
  status_display: string;
  checked_in_at: string;
  check_in_method: "qr" | "manual";
  method_display: string;
  edited_by_username: string | null;
  edit_reason: string | null;
}

export interface AuditLog {
  id: string;
  actor: string | null;
  actor_username: string;
  action: string;
  resource_type: string;
  resource_id: string;
  metadata: Record<string, unknown> | null;
  ip_address: string | null;
  user_agent: string;
  created_at: string;
}

export interface AdminDashboardData {
  users_total: number;
  users_active: number;
  students_total: number;
  instructors_total: number;
  programs_total: number;
  courses_total: number;
  courses_active: number;
  offerings_total: number;
  sessions_total: number;
  sessions_open: number;
  sessions_today: number;
  records_today: number;
  records_this_week: number;
  daily_trend: { date: string; count: number }[];
  status_breakdown: Partial<Record<AttendanceStatus, number>>;
  program_students: { program: string | null; students: number }[];
  high_absence_courses: {
    course_code: string;
    course_name: string;
    total_records: number;
    absent_count: number;
    absence_rate: number;
  }[];
}

export interface InstructorDashboardData {
  offerings: {
    id: string;
    course_code: string;
    course_name: string;
    term: string;
    enrolled: number;
    status: string;
  }[];
  sessions_today: number;
  open_session_id: string | null;
  total_records: number;
  total_absent: number;
  status_breakdown: Partial<Record<AttendanceStatus, number>>;
}

export interface StudentDashboardData {
  current_term: string | null;
  profile:
    | {
        student_code: string;
        first_name: string;
        last_name: string;
        email: string;
        username: string;
        program_name: string | null;
        class_group_name: string | null;
        academic_year_level: number;
        status: string;
        status_display: string;
      }
    | null;
  courses: { id: string; course_code: string; course_name: string; term: string }[];
  schedules: {
    id: string;
    course_code: string;
    course_name: string;
    weekday: number;
    weekday_display: string;
    start_time: string;
    end_time: string;
    classroom: string;
    status: string;
  }[];
  statistics: Record<AttendanceStatus, number>;
  recent_records: {
    course_code: string;
    session_date: string;
    status: AttendanceStatus;
    checked_in_at: string;
  }[];
}

export interface CheckInResult {
  attendance_session: string;
  course_code: string;
  course_name: string;
  session_date: string;
  status: AttendanceStatus;
  checked_in_at: string;
}

export interface ReportRow {
  student_id: string;
  student_code: string;
  student_name: string;
  present: number;
  late: number;
  absent: number;
  excused: number;
  eligible_sessions: number;
  attendance_rate: number;
}

export interface AttendanceReportData {
  rows: ReportRow[];
  total_closed_sessions: number;
  formula: string;
  note: string;
}
