# SAMS — Architecture

ระบบบริหารจัดการการเข้าเรียนผ่าน QR Code — Monorepo 2 ส่วนที่สื่อสารกันผ่าน REST API versioned

```
Student-Attendance-Project/
├── backend/                    # Django 6.1.2 + DRF 3.18.3
│   ├── config/                 # settings / urls / api_urls / wsgi / asgi
│   ├── common/                 # renderers, exceptions, pagination, csvutils, health
│   ├── apps/
│   │   ├── accounts/           # User + profiles + auth (login/refresh/logout/me)
│   │   ├── academics/          # programs, class_groups, academic_terms
│   │   ├── courses/            # courses, course_offerings, enrollments
│   │   ├── schedules/          # class_schedules, attendance_sessions (ทุกนัดเรียน)
│   │   ├── attendance/         # sessions lifecycle, check-in, records, QR
│   │   ├── reports/            # รายงาน + CSV export
│   │   ├── audit/              # audit logs (admin-only)
│   │   └── dashboard/          # dashboards ×3 (admin/instructor/student)
│   └── scripts/                # smoke & utility scripts ที่ใช้ทดสอบจริง
├── frontend/                   # Next.js 16.4.3 (App Router, TypeScript, Tailwind 4)
│   ├── app/
│   │   ├── login/
│   │   ├── admin/              # users, students, instructors, programs, class-groups,
│   │   │                       # academic-terms, courses, course-offerings, enrollments,
│   │   │                       # schedules, attendance-records, attendance-sessions,
│   │   │                       # audit-logs, reports, dashboard
│   │   ├── instructor/         # dashboard, courses, schedule, attendance (+ [sessionId] control room)
│   │   └── student/            # dashboard, courses, schedule, history, scan, profile
│   ├── components/             # CrudPage, DataTable (generic)
│   └── lib/                    # api.ts (axios + envelope + refresh interceptor), auth-context.tsx
├── docs/                       # เอกสารทั้งหมด
└── docker-compose.yml          # dev stack (backend + frontend)
```

## ข้อตกลงร่วม

- การ version ทำที่เส้นทาง: `/api/v1/...` (ดู `config/api_urls.py`)
- Timezone: `Asia/Bangkok`, locale `th` (USE_TZ=True เก็บ UTC)

## Response Envelope

ทุก response 2xx ของ API ถูก wrap ด้วย `common.renderers.SamsJSONRenderer` (ตั้งเป็น DEFAULT_RENDERER ทั้ง project — ครอบคลุมด้วย DRF views ทั้งแบบ ViewSet และ APIView):

```json
{
  "success": true,
  "message": "ข้อความที่อ่านง่ายสำหรับผู้ใช้",
  "data": { ... },
  "pagination": { "count": 20, "pages": 1, "current": 1, "next": null, "previous": null, "page_size": 20 }
}
```

- `pagination` เกิดเฉพาะ list view (StandardPagination, page_size=20)
- กรณี error: `{success: false, message, code, errors}` — ตัวอย่าง เช่น คาบไม่พร้อมเช็คชื่อ:

```json
{ "success": false, "message": "คุณเช็คชื่อในคาบนี้แล้ว", "code": "ATTENDANCE_ALREADY_EXISTS" }
```

- การแปลง error ให้เป็น envelope ทำใน `common.exceptions.sams_exception_handler`

## Authentication Flow (JWT)

- **Access token**: อายุสั้น (default 10 นาที, validate 1–240) — frontend เก็บ **ใน memory เท่านั้น** (ผ่าน `setAccessToken`), ห้าม localStorage
- **Refresh token**: rotation ทุกครั้งที่ใช้ (`ROTATE_REFRESH_TOKENS=True`), เก็บใน **HttpOnly cookie** ชื่อ `sams_refresh` (path=`/api/v1/auth/`, SameSite=Lax), ใช้ blacklist ร่วมด้วย (`BLACKLIST_AFTER_ROTATION=True`)
- **Frontend**: axios interceptor + `refreshSession()` แบบ **single-flight** — 401 → เรียก refresh หนึ่งครั้ง (กันเรียกซ้อนหลายทาบซ้ำ), เรียกไม่สำเร็จ → force logout
- **Backend**: ยิง cookie ให้มี flag `SECURE` เมื่อ DEBUG=False (ทดสอบจริง — browser (Chromium) ผ่าน localhost อ่าน Secure cookie ได้ระหว่างทดสอบ production stack)

## QR Attendance Flow

1. อาจารย์เปิดคาบเช็คชื่อ (`POST /api/v1/attendance/sessions/{id}/open/`) — token QR หมุนทุก 30 วินาที (TTL, validate 5–3600) แสดงใน control room `/instructor/attendance/[sessionId]` (QR SVG + countdown)
2. เซิร์ฟเวอร์เก็บ **เฉพาะ SHA-256 hash** ของ token (ไม่เก็บ token ดิบ) พร้อม unique เพื่อกัน replay (qr_tokens.hash unique)
3. นักศึกษาเช็คชื่อ (`POST /api/v1/attendance/check-in/`)
   - validate hash + TTL ผ่าน → บันทึก record สถานะ `present` / `late` (threshold default 15 นาที, ปรับได้ใน .env)
   - unique constraint `(attendance_session_id, student_id)` บน attendance_records — ทดสอบจริงด้วย 2 threads สร้างพร้อมกันได้ record เดียว, ฝั่งอื่น error 409 `ATTENDANCE_ALREADY_EXISTS`
4. ปิดคาบ (`/close/`) → นักเรียนที่ไม่ได้เช็คชื่อถูกสร้าง record `absent` อัตโนมัติ (`/cancel/` ยกเลิกคาบ)
5. คาบหยุดชั่วคราว (`/pause/`) ได้ และเปิดต่อได้ (service `open_session` รองรับ `paused → open` — ตาม flow ที่ทดสอบจริงใน UI)

## RBAC

ทุก ViewSet ตรวจ role ทั้ง serializer และ `get_queryset()` — ตัวอย่าง:

- นักศึกษาเห็น attendance records ของตัวเองเท่านั้น
- อาจารย์เข้าถึง/แก้ไขเฉพาะคาบของตัวเอง (`SessionScopeMixin`)
- audit logs เห็นได้เฉพาะ admin (ทดสอบจริง: instructor/student เจอ 403)

## CSV ป้องกัน Injection

- **Import** (`/users/import-students/`, field ชื่อ `file`): sanitize formula injection ทุก field ผ่าน `common.csvutils.sanitize_csv_value` (เช่น `=HYPERLINK(...)` → `'ฉ้อฉล(ถูกแก้)`), throttle `csv_import: 5/hour`
- **Export**: `rows_to_csv_bytes` เข้า **UTF-8-BOM** เพื่อ Excel อ่านภาษาไทยถูกต้อง (ยืนยันจริงที่ API level และปุ่ม export หน้า reports)

## Health & Docs

- `GET /api/v1/health/` — no auth, ping DB, envelope `{service, version, database}`
- `GET /api/v1/schema/` + `GET /api/v1/docs/` — OpenAPI (drf-spectacular) ที่มี response envelope อัตโนมัติ
