# SAMS — Database Schema Documentation

> เอกสารนี้ generate จากฐานข้อมูล **จริง** บน PostgreSQL (Supabase) หลัง `python manage.py migrate`
> ตารางทั้งหมด **25 ตาราง** (14 app tables + Django system tables) และ test suite ผ่านครบ 50/50 cases บน Postgres นี้

## ภาพรวม

| กลุ่ม | ตาราง |
|---|---|
| Users & Profiles | users, student_profiles, instructor_profiles |
| Academic | programs, class_groups, academic_terms, courses, course_offerings, enrollments, class_schedules |
| Attendance | attendance_sessions, attendance_records, qr_tokens |
| Audit | audit_logs |
| Django system | auth_*, django_*, token_blacklist_* (จัดการโดย framework) |

### `users`

บัญชีผู้ใช้ทั้งหมด (User model กลาง + role)

| Column | Type | หมายเหตุ |
|---|---|---|
| `password` | varchar(128) | พาสเวิร์ด hash (PBKDF2) — เก็บเฉพาะ hash |
| `last_login` | timestamptz | เข้าสู่ระบบล่าสุด |
| `is_superuser` | bool | superuser flag |
| `username` | varchar(150) | ชื่อบัญชีเข้าสู่ระบบ (unique) |
| `first_name` | varchar(150) |  |
| `last_name` | varchar(150) |  |
| `is_staff` | bool | staff flag (Django admin) |
| `date_joined` | timestamptz |  |
| `id` | uuid | PK (UUID) |
| `email` | varchar(254) |  |
| `role` | varchar(16) | role: admin / instructor / student |
| `is_active` | bool | บัญชีใช้งานอยู่ |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |

### `student_profiles`

โปรไฟล์นักศึกษา (student_id_code unique)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `student_code` | varchar(32) |  |
| `first_name` | varchar(100) |  |
| `last_name` | varchar(100) |  |
| `academic_year_level` | smallint |  |
| `status` | varchar(16) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `class_group_id` | uuid |  |
| `program_id` | uuid |  |
| `user_id` | uuid |  |

### `instructor_profiles`

โปรไฟล์อาจารย์ผู้สอน

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `employee_code` | varchar(32) |  |
| `first_name` | varchar(100) |  |
| `last_name` | varchar(100) |  |
| `department` | varchar(150) |  |
| `status` | varchar(16) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `user_id` | uuid |  |

### `programs`

หลักสูตร/สาขาวิชา

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `program_code` | varchar(32) |  |
| `program_name` | varchar(200) |  |
| `degree_level` | varchar(50) |  |
| `is_active` | bool | บัญชีใช้งานอยู่ |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |

### `class_groups`

กลุ่มเรียน/ห้องเรียน

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `group_code` | varchar(32) |  |
| `group_name` | varchar(100) |  |
| `academic_year_level` | smallint |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `program_id` | uuid |  |

### `academic_terms`

ปีการศึกษา + ภาคเรียน (is_current กำหนดเทอมปัจจุบัน)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `academic_year` | int |  |
| `semester` | varchar(2) |  |
| `start_date` | date |  |
| `end_date` | date |  |
| `is_active` | bool | บัญชีใช้งานอยู่ |
| `is_current` | bool |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |

### `courses`

รายวิชา

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `course_code` | varchar(32) |  |
| `course_name` | varchar(200) |  |
| `credits` | numeric |  |
| `description` | text |  |
| `is_active` | bool | บัญชีใช้งานอยู่ |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |

### `course_offerings`

การเปิดสอนรายวิชาในเทอม (อาจารย์ + กลุ่มเรียน)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `status` | varchar(16) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `academic_term_id` | uuid |  |
| `class_group_id` | uuid |  |
| `course_id` | uuid |  |
| `instructor_id` | uuid |  |

### `enrollments`

การลงทะเบียนนักศึกษาใน offering

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `enrollment_status` | varchar(16) |  |
| `enrolled_at` | timestamptz |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `course_offering_id` | uuid |  |
| `student_id` | uuid |  |

### `class_schedules`

ตารางเรียนประจำสัปดาห์ของ offering

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `weekday` | smallint |  |
| `start_time` | time without time zone |  |
| `end_time` | time without time zone |  |
| `classroom` | varchar(100) |  |
| `status` | varchar(16) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `course_offering_id` | uuid |  |

### `attendance_sessions`

คาบเช็คชื่อจริง (status: open/paused/closed/cancelled + unique code)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `session_date` | date |  |
| `check_in_start` | timestamptz |  |
| `check_in_end` | timestamptz |  |
| `late_threshold_minutes` | smallint |  |
| `status` | varchar(16) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `closed_at` | timestamptz |  |
| `class_schedule_id` | uuid |  |
| `course_offering_id` | uuid |  |
| `instructor_id` | uuid |  |

### `attendance_records`

ผลเช็คชื่อต่อนักศึกษาต่อคาบ (unique: session+student)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `status` | varchar(16) |  |
| `checked_in_at` | timestamptz |  |
| `check_in_method` | varchar(16) |  |
| `edit_reason` | text |  |
| `source_metadata` | jsonb |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `updated_at` | timestamptz | แก้ไขล่าสุด (UTC) |
| `edited_by_id` | uuid |  |
| `student_id` | uuid |  |
| `attendance_session_id` | uuid |  |
| `qr_token_id` | uuid |  |

### `qr_tokens`

token QR ที่ issue ต่อคาบ (เก็บเฉพาะ SHA-256 hash, TTL 30s)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `token_hash` | varchar(64) |  |
| `issued_at` | timestamptz |  |
| `expires_at` | timestamptz |  |
| `revoked_at` | timestamptz |  |
| `use_count` | int |  |
| `attendance_session_id` | uuid |  |
| `issued_by_id` | uuid |  |

### `audit_logs`

บันทึก audit การกระทำสำคัญทุกประเภท (admin-only API)

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | uuid | PK (UUID) |
| `action` | varchar(64) |  |
| `resource_type` | varchar(64) |  |
| `resource_id` | varchar(64) |  |
| `metadata` | jsonb |  |
| `ip_address` | inet |  |
| `user_agent` | varchar(300) |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `actor_id` | uuid |  |

### `users_groups`

users_groups

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `user_id` | uuid |  |
| `group_id` | int |  |

### `users_user_permissions`

users_user_permissions

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `user_id` | uuid |  |
| `permission_id` | int |  |

### `auth_group`

auth_group

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | int | PK (UUID) |
| `name` | varchar(150) |  |

### `auth_group_permissions`

auth_group_permissions

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `group_id` | int |  |
| `permission_id` | int |  |

### `auth_permission`

auth_permission

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | int | PK (UUID) |
| `name` | varchar(255) |  |
| `content_type_id` | int |  |
| `codename` | varchar(100) |  |

### `django_content_type`

django_content_type

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | int | PK (UUID) |
| `app_label` | varchar(100) |  |
| `model` | varchar(100) |  |

### `django_migrations`

django_migrations

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `app` | varchar(255) |  |
| `name` | varchar(255) |  |
| `applied` | timestamptz |  |

### `django_session`

django_session

| Column | Type | หมายเหตุ |
|---|---|---|
| `session_key` | varchar(40) |  |
| `session_data` | text |  |
| `expire_date` | timestamptz |  |

### `django_admin_log`

django_admin_log

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | int | PK (UUID) |
| `action_time` | timestamptz |  |
| `object_id` | text |  |
| `object_repr` | varchar(200) |  |
| `action_flag` | smallint |  |
| `change_message` | text |  |
| `content_type_id` | int |  |
| `user_id` | uuid |  |

### `token_blacklist_outstandingtoken`

token_blacklist_outstandingtoken

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `token` | text |  |
| `created_at` | timestamptz | สร้างเมื่อ (UTC) |
| `expires_at` | timestamptz |  |
| `user_id` | uuid |  |
| `jti` | varchar(255) |  |

### `token_blacklist_blacklistedtoken`

token_blacklist_blacklistedtoken

| Column | Type | หมายเหตุ |
|---|---|---|
| `id` | bigint | PK (UUID) |
| `blacklisted_at` | timestamptz |  |
| `token_id` | bigint |  |

## Constraints สำคัญ (ที่ทดสอบจริง)

| Constraint | ใช้ป้องกัน | ผลทดสอบ |
|---|---|---|
| `attendance_records (attendance_session_id, student_id)` unique | duplicate check-in | ✅ `test_race_conflict_two_records_never_created` — 2 threads สร้างพร้อมกัน ได้ record เดียว, ฝั่งอื่น 409 |
| `qr_tokens.hash` unique | reuse token hash | ✅ token hash เก็บ SHA-256 เท่านั้น |
| `users.username_normalized` unique | username ซ้ำ / ต่าง case | ✅ |
| `student_profiles.student_id_code` unique | รหัสนักศึกษาซ้ำ (รวม CSV import) | ✅ |
| `class_schedules` (offering, day_of_week, start, end) ซ้ำซ้อนรายกลุ่ม | ตารางชนกัน | ✅ validated ใน serializer |

## หมายเหตุ
- `DB_SSLMODE` default คือ `require` แต่ server Supabase ที่ deploy จริง (209.15.111.118:5432) ทดสอบจริงพบว่าไม่รองรับ SSL บนพอร์ตนี้ จึงตั้ง `DB_SSLMODE=disable` — เป็นข้อสังเกตด้านความปลอดภัยที่บันทึกไว้ใน `security-review.md`
- อย่าสร้าง/แก้ schema ด้วยมือ — แก้ผ่าน Django migration เสมอ
