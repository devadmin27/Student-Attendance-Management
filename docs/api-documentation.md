# SAMS — API Documentation

Base URL: **`http://<host>/api/v1/`** | OpenAPI schema: `/api/v1/schema/` | Swagger UI: `/api/v1/docs/`

ทุก endpoint ใช้ JWT Bearer (`Authorization: Bearer <access>`) ยกเว้นที่ระบุ AllowAny
สถานะทดสอบ: ✅ = ทดสอบและยืนยันจริงระหว่าง dev (ดู [`test-report.md`](test-report.md))

## Response Envelope

ทุก response 2xx (ผ่าน `SamsJSONRenderer`):

```json
{ "success": true, "message": "...", "data": { ... }, "pagination": { "count": 0, "pages": 0, "current": 0, "next": null, "previous": null, "page_size": 20 } }
```

Error response (ผ่าน `sams_exception_handler`):

```json
{ "success": false, "message": "...", "code": "ERROR_CODE", "errors": { ... } }
```

**Error code ที่รวมเจอผ่านการทดสอบจริง:** `ATTENDANCE_ALREADY_EXISTS` (409 — duplicate check-in), `401` (token หมดอายุ/invalid → frontend auto-refresh), `403` (RBAC — เช่น instructor เรียก dashboard ของ admin, student เรียก audit logs)

## 1. Authentication ✅

| Method | Path | Auth | คำอธิบาย | ปรับการทำงาน |
|---|---|---|---|---|
| POST | `auth/login/` | — | login ตาม Username/Password + role | ตอบ access token + `data.user`, set cookie `sams_refresh` (HttpOnly, path=`/api/v1/auth/`, SameSite=Lax) |
| POST | `auth/refresh/` | cookie | rotate refresh + access ใหม่ | refresh เก่าถูก blacklist / rotate |
| POST | `auth/logout/` | user | ลบ cookie + blacklist | — |
| GET | `auth/me/` | user | ข้อมูลผู้ใช้ + profile | ✅ ใช้ hydrate หลัง reload ผ่าน refresh ได้จริง |

## 2. Dashboard ✅ (ทดสอบทั้งสาม role)

| Method | Path | Role | คำอธิบาย |
|---|---|---|---|
| GET | `dashboard/admin/` | admin | stats + charts (ผล 17 keys, `users_total=1` ตอน seed ผลิต) |
| GET | `dashboard/instructor/` | instructor | stats คาบของตัวเอง + ปุ่มเข้า control room |
| GET | `dashboard/student/` | student | cards + ประวัติของนักเรียน (ทดสอบ 4 cards) |

## 3. Core Routers (ModelViewSets, ทั้งหมดมี list/detail/create/update/delete + pagination)

| Prefix | Group | RBAC เขียน | RBAC อ่าน |
|---|---|---|---|
| `users/` | บัญชีผู้ใช้ | admin | admin (ผ่าน UI admin: 11 users ทดสอบจริง) |
| `students/` / `instructors/` | profiles | admin | ตาม scope |
| `programs/` / `class-groups/` / `academic-terms/` | academic ตั้งค่า | admin | admin |
| `courses/` / `course-offerings/` / `enrollments/` | รายวิชา / เปิดสอน / ลงทะเบียน | admin / instructor | instructor (ของตัวเอง) |
| `class-schedules/` | ตารางเรียนรายสัปดาห์ | admin/instructor | instructor |
| `attendance/sessions/` | คาบเช็คชื่อ | instructor (ของตัวเอง) | admin + instructor |
| `attendance/records/` | ผลเช็คชื่น (PATCH ต้องมี `edit_reason` และระบบบันทึก `edited_by`) | instructor / admin | student (ของตัวเอง) |

### Actions บน `attendance/sessions/{id}/` ✅ (ทดสอบทุกตัวผ่าน UI จริง)

| Path | คำอธิบาย |
|---|---|
| `POST open/` | เริ่มคาบ — รองรับ `paused → open` + QR token เริ่มหมุน |
| `POST pause/` | หยุดชั่วคราว (ปุ่ม ⏸ ใน control room) |
| `POST close/` | ปิดคาบ — คนที่ไม่เข้าจะถูก auto-absent (ทดสอบจริง: 6 records ถูกสร้าง) |
| `POST cancel/` | ยกเลิกคาบ |
| `GET qr-token/` | token QR ปัจจุบัน + `ttl` (ทดสอบ: ttl 29s, raw token length 43 และ hash SHA-256) |
| `GET roster/` | รายชื่อนักเรียน + สถานะ (ทดสอบ: roster 65000001-06 อัปเดตเรียลไทม์) |

## 4. Attendance / Check-in ✅

| Method | Path | Auth | Response |
|---|---|---|---|
| POST | `attendance/check-in/` | student (throttle `checkin: 20/min`) | ส่ง token → `present`/`late`; token หมดอายุ/ใช้ซ้ำ → 409 / 400 |
| GET | `attendance/my-history/` | student | ประวัติเช็คชื่อของตัวเอง (ทดสอบ UI: 16 rows) |

## 5. Reports ✅

| Method | Path | Role | คำอธิบาย |
|---|---|---|---|
| GET | `reports/` ทั้งชุด (admin: `/admin/reports` / instructor) | admin/instructor | ข้อมูลตาราง (ทดสอบ: 6 rows) |
| GET | export (CSV) | admin/instructor | **UTF-8-BOM** + sanitize formula injection (ยืนยัน bytes มี `EF BB BF`) |

## 6. CSV Import (Students) ✅

| Method | Path | หมายเหตุ |
|---|---|---|
| POST | `users/import-students/` | **multipart/form-data field ชื่อ `file`** (ไม่ใช่ `csv_file`); sanitize `=HYPERLINK` ให้เป็น `'ฉ้อฉล(ถูกแก้)` ผ่าน smoke script จริง; throttle `5/hour` |

## 7. Audit Logs ✅

| Method | Path | Role |
|---|---|---|
| GET | `audit/...` (admin-only) | 20 rows ทดสอบจริง; instructor/student ได้ 403; แก้ attendance record สร้าง log พร้อม `edited_by` username (แก้ไม่ได้/ลบไม่ได้ทาง API) |

## 8. Health / Docs (no auth)

| Method | Path | Response |
|---|---|---|
| GET | `health/` | envelope `{service, version, database}`; DB unreachable → 503 |
| GET | `schema/`, `docs/` | OpenAPI JSON + Swagger UI |

## Throttle Rates (ตามจริงใน settings.py)

- anon: 100/hour, user: 600/hour
- **login: 10/min · checkin: 20/min · csv_import: 5/hour**

## ตัวอย่าง Request สำคัญ

```bash
# Login (รับ access token + set sams_refresh cookie)
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -c cookies.txt \
  -d '{"username":"admin","password":"..."}'

# Check-in (student)
curl -X POST http://localhost:8000/api/v1/attendance/check-in/ \
  -H "Authorization: Bearer <access>" -H "Content-Type: application/json" \
  -d '{"token":"<raw QR token>"}'
```

## ข้อควรปฏิบัติเรียกใช้จริง

- Frontend NEVER เก็บ refresh token ใน JS — มีอยู่ใน HttpOnly cookie เท่านั้น (`withCredentials` + CORS allow credentials)
- ทุก patch attendance record ถูกบันทึกใน audit logs (username + edit_reason + timestamp) — ผ่านการทดสอบจริง
