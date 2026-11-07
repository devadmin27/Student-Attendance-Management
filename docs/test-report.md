# SAMS — Test Report

**วันที่:** 2026-10-28 · **สถานะ:** ผ่าน ทั้ง backend และ UI ใน browser
รายงานนี้รวมเฉพาะสิ่งที่ **ทดสอบและยืนยันจริง** ระหว่างพัฒนา — หน้าจอ/API ที่ไม่ได้รันจะไม่ถูกอ้างว่าผ่าน

## 1. Django Test Suite

| ชุด | ผล |
|---|---|
| SQLite (dev, DEBUG=True) | ✅ 50/50 test cases ผ่าน |
| **Postgres (Supabase จริง)** | ✅ 50/50 test cases ผ่าน (รวม race test) |
| `test_race_conflict_two_records_never_created` | ✅ สอง thread สร้าง record พร้อมกัน — unique constraint กันได้ ได้ record เดียว, อีกฝั่ง 409 |

`manage.py migrate` บน Postgres จริง → **25 ตาราง** ครบ (ดู [`database-schema.md`](database-schema.md))

## 2. API smoke (เรียกจริงผ่าน HTTP)

| ทดสอบ | ผล | หมายเหตุ (หลักฐาน) |
|---|---|---|
| login / me / refresh / logout | ✅ | envelope ครบ, cookie `sams_refresh` HttpOnly; refresh ต่ออายุ + rotate; token เก่าถูก blacklist |
| Dashboard ×3 (admin/instructor/student) | ✅ | keys ครบทุก role; admin ที่ seed ผลิต `users_total=1` (17 keys) |
| sessions list + detail | ✅ | envelope ผ่าน `SamsJSONRenderer` |
| QR issue | ✅ | `ttl=29s`, raw token length 43, ระบบเก็บเฉพาะ SHA-256 hash |
| Check-in `present` / `late` | ✅ | threshold ตาม env (default 15 นาที) |
| Duplicate check-in | ✅ | **409 code=`ATTENDANCE_ALREADY_EXISTS`** — "คุณเช็คชื่อในคาบนี้แล้ว" |
| Roster | ✅ | รายชื่อ 65000001–06 + สถานะล่าสุด |
| Records PATCH (พร้อม `edit_reason`) | ✅ | audit บันทึก username ผู้แก้ (instructor) จริง |
| CSV Export | ✅ | bytes เริ่มด้วย `EF BB BF` (UTF-8-BOM) — Excel ไทยถูก |
| CSV Import | ✅ | field ชื่อ `file`; sanitize `=HYPERLINK(...)` → `'ฉ้อฉล(ถูกแก้)` (smoke_st03 แก้ทันที, smoke_st04 ที่นำเข้าใหม่ได้ sanitize ตามเกณฑ์) |
| Audit logs | ✅ | admin เท่านั้น (instructor/student ได้ 403), payload เห็น 20 rows |
| RBAC ทุกชั้น | ✅ | instructor เรียก dashboard/admin → 403 ฯลฯ |
| Health / schema / docs | ✅ | health ตอบ database=connected; OpenAPI + Swagger UI ใช้งานได้ |
| Throttle | ✅ (ตั้งค่าจริง) | login 10/min · checkin 20/min · csv_import 5/hour · anon 100/hour · user 600/hour |

## 3. UI ทดสอบจริงใน Browser (localhost:3000, Chromium)

### Admin (login → dashboard)
| สร้างบัญชีผู้ใช้ยืนยันจริง (UI) | ✅ — admin/instructor/student สร้างสำเร็จสังเกต toast "เพิ่มข้อมูลสำเร็จ", role แสดงถูกหมวด; รหัสอ่อน/ชื่อซ้ำ → toast โชว์สาเหตุราย field; email ว่างผ่าน |
| ลบบัญชีผู้ใช้ (UI) | ✅ — instructor ที่ไม่มี profile → 204 + toast สำเร็จ (หลังแก้ bug #6/#7); ลบตัวเอง → กันด้วย 400 "ไม่สามารถลบตัวของตัวเองได้" |
- ✅ กราฟ 2 ชุด (recharts) + การ์ดสถิติ; หน้า users แสดง 11 users
- ✅ students + ฟอร์ม CSV import · audit-logs (20 rows) · reports (6 rows + ปุ่ม export) · attendance-records (20 rows) · attendance-sessions (18 rows)

### Instructor
- ✅ login → control room `/instructor/attendance/[sessionId]`: QR SVG render + countdown "5 วินาที"
- ✅ roster นักศึกษา 65000001–06 อัปเดตเรียลไทม์
- ✅ ปุ่ม ⏸ หยุดชั่วคราว → ▶ เปิดต่อ (QR หมุนต่อ)
- ✅ ปิดคาบ → **auto-absent 6 records** ทันที
- ✅ ยกเลิกคาบทำงานถูก

### Student
- ✅ login `student05` → dashboard (16 rows + 4 cards) · courses · history · profile (PDPA read-only)
- ✅ scan โหมดกรอก token ด้วยมือ → check-in สำเร็จ
- ✅ สแกน/เช็คซ้ำ → 409 "คุณเช็คชื่อในคาบนี้แล้ว"
- ✅ logout สำเร็จ

## 4. Production stack smoke (Supabase Postgres ✅)

| ลำดับ | ผล |
|---|---|
| login admin ผลิต (`admin`) | ✅ access + refresh cookie |
| `GET /me` | ✅ envelope ครบ |
| `GET /dashboard/admin/` | ✅ 17 keys, `users_total=1` |
| `POST /refresh/` (browser localhost) | ✅ rotate สำเร็จ — Chromium ยอมรับ Secure cookie บน localhost |
| Reload หน้า `/admin/dashboard` ×2 | ✅ session ค้าง ไม่ force-logout (single-flight refresh ทำงานถูกต้อง) |

## 5. Frontend ทดสอบ

| ทดสอบ | ผล |
|---|---|
| `npm run lint` | ✅ 0 ปัญหา |
| `npm run build` | ✅ 32/32 routes |

> ข้อสังเกตจริง: ไม่รัน `npm run build` ขณะ `next dev` กำลังทำงาน — ชน `.next` โฟลเดอร์และทำให้ HMR พัง

## 6. Bug ที่พบจริงระหว่างทดสอบและแก้ไขแล้ว

| # | อาการ | สาเหตุ | แก้ไข | หลักฐานหลังแก้ |
|---|---|---|---|---|
| 1 | สร้าง profile อัตโนมัติได้รหัส `auto-<UUID 36>` ซึ่งยาวเกิน `varchar(32)` — พังบน Postgres แต่ SQLite mask ไม่เห็น | fallback code ตอนสร้าง profile สร้างค่าที่ยาวไป | เปลี่ยน fallback เป็น `auto-<pk.hex[:12]>` (`apps/accounts/models.py`) | migrate/import บน Postgres จริงไม่พังอีก |
| 2 | session เคยค้างสถานะ paused และไม่เปิดใหม่ด้วย `open` | state transition ไม่รองรับ `paused → open` | service `open_session` ปรับให้รองรับ `paused → open` | ⏸ → ▶ ทำงานเต็มรอบใน UI |
| 3 | refresh token ถูก rotate ซ้อนหลายครั้งต่อ session เดียว | frontend เรียก refresh หลายแหล่งพร้อมกัน | `refreshSession()` single-flight · AuthContext เรียกผ่านตัวเดียว | reload ×2 — session ค้าง ไม่ force logout |
| 4 | import ภาษาไทยเห็นเป็น `?` บน Windows | PowerShell console encoding ทำค่า display ผิด | ใช้สคริปต์ Python (UTF-8) + ไฟล์ BOM สำหรับ verify — ไบต์ใน DB จริงถูก (ยืนยันด้วย Python) | ข้อมูลไทยเก็บและแสดงผลถูก |

| 5 | สร้างบัญชีจาก UI → 400 ข้อมูลที่ส่งมาไม่ถูกต้อง | `CrudPage.buildPayload` เงื่อนไขกลับด้าน — ข้าม `createOnly` fields (password) บน create + optional ว่างถูกส่งเป็น `null` ("ฟิลด์นี้จำเป็นต้องมีค่า") | ส่ง createOnly บน create, ข้าม null ของ optional ทั้ง create/update (`frontend/components/CrudPage.tsx`) | ✅ POST 201 จริงผ่าน UI |
| 6 | ลบบัญชี instructor → 500 | reverse OneToOne ที่ไม่มี profile (`user.student_profile`) raise `RelatedObjectDoesNotExist` | guard `except ObjectDoesNotExist` ใน `destroy` (`apps/accounts/views.py`) | ✅ DELETE 204 จริงผ่าน UI |
| 7 | ลบสำเร็จ (204) แต่ UI โชว์ "ลบข้อมูลไม่สำเร็จ" | frontend บังคับ envelope `success: true` — 204 ไม่มี body | `samsRequest` ยอมรับ 204/empty envelope (`frontend/lib/api.ts`) | ✅ DELETE 204 → toast "ลบข้อมูลสำเร็จ" |
| 8 | error validation โชว์เพียงข้อความรวม ๆ | toast แสดงเฉพาะ `message` โดยไม่รวม `errors` ราย field | summarize `errors` per-field แล้ว concat ทั้ง `samsRequest` และ response interceptor (`frontend/lib/api.ts`) | ✅ ทดสอบ: weak password → "password: This password is too common.", duplicate username → "username: ชื่อผู้ใช้นั้นได้ถูกใช้ไปแล้ว" |

## 7. ข้อสังเกตสภาพแวดล้อมผลิต

- Server Postgres ที่ใช้จริง **ไม่รองรับ SSL** บนพอร์ต 5432 → `DB_SSLMODE=disable` (บันทึกใน [`security-review.md`](security-review.md) พร้อม mitigation)
- ผลิต seed เฉพาะ `admin` — ควรเปลี่ยนรหัสผ่านหลังใช้จริง

## 8. Production deploy จริงบน Coolify (2026-10-29)

สถาปัตยกรรมที่ deploy: Coolify **Docker Compose resource เดียว** (proxy → backend/frontend), โดเมนร่วม `https://sams.scphtrang.ac.th` ผ่าน Coolify Traefik (commit `392d712` → `76a4541` → `b67af63`)

### ตรวจ URL production จริง (ผ่าน HTTP ทุกตัว)

| URL | ผล | ยืนยัน |
|---|---|---|
| `/` | ✅ 200 | Next.js ไทย (`lang="th"`, title "SAMS") |
| `/login` | ✅ 200 | หน้า login frontend |
| `/admin/dashboard` | ✅ 200 | **Frontend จริง** (`/_next` assets) — ไม่ใช่ Django admin |
| `/api/v1/health/` | ✅ 200 | `database: "connected"` |
| `/django-admin/login/` | ✅ 200 | หน้า login Django admin (ภาษาไทย) |
| `/api/v1/schema/` + `/api/v1/docs/` | ✅ 200 ทั้งคู่ | OpenAPI JSON (135 KB) + Swagger UI |

### Bug ที่พบจาก production จริงและแก้แล้ว

| # | อาการ | สาเหตุ (ยืนยัน traceback จริง) | แก้ไข | หลักฐานหลังแก้ (production จริง) |
|---|---|---|---|---|
| 9 | login frontend ด้วย admin แล้วถูก redirect ไป `/admin/login` (Django admin) เข้า `/admin/dashboard` ไม่ได้ | nginx route เดิม `^/(api|admin|static)/` → Django; คู่กับ `urls.py` `path("admin/")` — **prefix `/admin/` ชนกันระหว่าง Django admin กับหน้า dashboard ของ Next.js** (`filterHome(admin) = "/admin/dashboard"`) | ย้าย Django admin ไป `path("django-admin/", ...)` (`backend/config/urls.py`, รอบ `ccab5d3`) และ nginx route เป็น `^/(api|django-admin|static)/` | probe จริง: `/admin/dashboard` → 200 หน้า Next.js; `/django-admin/login/` → 200 |
| 10 | เพิ่มอาจารย์หน้า `/instructors` → 500 "เกิดข้อผิดพลาดในการเชื่อมต่อระบบ" | `UserManager.create_user(role="instructor")` สร้าง InstructorProfile แล้วแถวเดียว (`_ensure_profile`); view ไป `InstructorProfile.objects.create(user=user, ...)` **ซ้ำ** → `UniqueViolation: instructor_profiles_user_id_key` (Postgres); และไม่มี transaction — เมื่อพังกลางคัน user กลางคันถูก commit ค้างใน DB | `get(user=user)` + update field ภายใน `transaction.atomic()` + จับ `IntegrityError` → **400 "มีบัญชีหรือรหัสพนักงานนี้อยู่แล้ว"** (`ec36505`) | probe จริง: POST 201 "เพิ่มอาจารย์สำเร็จ"; POST ซ้ำ → 400 DUPLICATE; user กลางคันที่ค้างถูกลบ (204) — DB กลับสู่ state เดิม |
| 11 | เพิ่มนักศึกษาหน้า `/students` → 500 (แบบเดียวกับ #10) | `StudentCreateSerializer.create` รัน `User.objects.create_user(role="student")` (สร้าง StudentProfile auto) แล้ว `StudentProfile.objects.create(user=with_user, **validated)` **ซ้ำ** → ชน unique OneToOne บน Postgres; CSV import ไม่เกี่ยว (ใช้ `user.student_profile` ที่มีอยู่แล้ว) | แก้ serializer: `get(user=with_user)` + อัปเดต field ที่ validate แล้วทั้งหมด ภายใน `transaction.atomic()` + `IntegrityError` → ValidationError 400 (`b8a53b8`) | ยืนยัน flow ใหม่บน Postgres จริง (rollback sim): student_code ถูกตั้งจาก payload + Django test 50/50 ผ่าน |

### ข้อสังเกตการทดสอบ

- ทดสอบ bug #10/#11 ทำโดย probe API จริงด้วย **transaction rollback** บน Postgres ผลิต — ไม่ทิ้งข้อมูลค้าง; ทุกครั้งที่เกิด user กลางคันมี DELETE account (204) เก็บกวาดให้เสมอ
- Probe จากภายนอก: Python urllib ธรรมดา UA `sams-probe/1.0` — ผ่าน Cloudflare (opener ที่มี cookie เก่าอาจตอบ 403 ลวง ผิดกับ UA/headers ธรรมดา)

## 9. CRUD ทุกตาราง + เปิดเช็คชื่อเต็มรอบบน production (2026-10-30)

สร้างข้อมูลทดสอบชั่วคราว (prefix `SCRT*`) ครบวงจร ทดสอบบน API ผลิต แล้วลบให้ครบท้ายรอบ (บัญชี/แถวทดสอบทั้งหมดไม่ค้าง)

### ตาราง CRUD (ถูกต้องครบทุกขั้นบน Postgres จริง)

| ตาราง | POST | GET detail | PATCH | duplicate guard | หมายเหตุ |
|---|---|---|---|---|---|
| programs | ✅ 201 | ✅ 200 | ✅ | ✅ ซ้ำ → 400 | |
| class-groups | ✅ 201 | ✅ 200 | ✅ | ✅ 400 | กระแทก program FK |
| academic-terms | ✅ 201 | ✅ 200 | ✅ | ✅ (year+semester) 400 | ปี<พ.ศ. / end<start → 400 |
| courses | ✅ 201 | ✅ 200 | ✅ | ✅ 400 | credits >12 → 400 |
| course-offerings | ✅ 201 | ✅ 200 | ✅ (status) | uniq (course+term+group) | |
| enrollments | ✅ 201 | — | ✅ (dropped↔enrolled) | ✅ ลงซ้ำ 400 | cancelled offering → 400 |
| class-schedules | ✅ 201 | ✅ 200 | ✅ | | weekday 0-6 |
| users | ✅ 201 (ทุก role) | ✅ | PATCH | duplicate → 400 | DELETE มีบั๊ก #12 (ล่าสุดแก้แล้ว) |
| students | ✅ 201 (ใช้ CSV/UI ผ่าน; ดู #11) | ✅ 200 (list + search) | — | | |

### /attendance เปิดเช็คชื่อเต็มรอบ (ผ่านบัญชีอาจารย์ + นักศึกษาทดสอบจริง) — 25/25 PASS

สร้างคาบ `scheduled` → `open` → ออก QR (`qr-token` — rotate ได้ ทุกครั้ง token ใหม่) → นักศึกษา add `POST /attendance/check-in/` (status `present`) → เช็คซ้ำ → **409** → roster อัปเดตเรียลไทม์ → PATCH record (`excused` + `edit_reason`) → `pause` → `open` (resume) → สร้างคาบที่สอง (วันถัดไป) → `cancel` → สร้างคาบซ้ำวันเดียวกัน → **409** `SESSION_ALREADY_EXISTS` → `close` → เช็คชื่อหลังปิด → 400/409 ตามออกแบบ

### RBAC ที่ยืนยันในรอบนี้

- instructor → GET /users/ → 403 · student → GET /users/ และ GET /attendance/sessions/ → 403 ตาม hierarchy

### Bug ใหม่ที่พบ/แก้ในรอบนี้

| # | อาการ | สาเหตุ | สถานะ |
|---|---|---|---|
| 12 (แก้แล้ว push `c4a13d1`) | DELETE /users/ ตัวที่มี audit log → 500 | `AuditLog.actor` PROTECT — append-only audit ไม่อนุญาตลบ user; destroy ไม่จับ `ProtectedError` | แก้ destroy ให้เตือน "ระงับบัญชีแทนการลบ" (soft delete) — deploy แล้วยืนยันจริงบน prod: DELETE user มี audit → 200 "ระงับ" + `is_active=False`; ไม่มี audit → 204 hard delete |
| 13 (แก้แล้ว push `38c5173` + `44672b2`) | รายงานจากผู้ใช้จริง: หน้า `/attendance` instructor กด "สร้างคาบเช็คชื่อ" → 500 ("เกิดข้อผิดพลาดในการเชื่อมต่อระบบ") | บัญชี instructor ที่ไม่มี InstructorProfile (สร้างผ่านหน้า Users ได้บัญชีเปล่า) — serializer/view เข้าถึง `user.instructor_profile` ตรง ๆ → `RelatedObjectDoesNotExist` → 500; และก่อนแก้ instructor ไม่มี profile **เห็น sessions/records ของทุกคน** (fallback ไป unscoped queryset) | แก้ 3 ชั้น: 400 `NO_INSTRUCTOR_PROFILE` ข้อความชัดทั้ง view + serializer; scoping ของ sessions + records **fail-closed** (queryset ว่างถ้าไม่มี profile) — ยืนยันจริงบน prod หลัง deploy `44672b2`/`c3ea5b1` (2026-10-30): bare instructor POST session → **400 `NO_INSTRUCTOR_PROFILE`** ข้อความชัด (ไม่ใช่ 500) ✅ · GET sessions/records → ว่าง (fail-closed) ✅ · POST บัญชีปกติ → 201 + DELETE → 204 ✅ · และผู้ใช้จริง (`nawat`) สร้างคาบ AI ผ่าน `/attendance` สำเร็จ end-to-end จนปิดคาบ (status closed) ✅ |

### ข้อสังเกตด้านโครงสร้าง infra ผลิต

- มี **ช่วงเวลา** ที่ request รำวรายสลับ 503 "no available server" (Cloudflare) และ 401 `NOT_AUTHENTICATED` แบบไม่อธิบายได้ด้วย app-token — หายเองในหลายนาที. สันนิษฐานว่ามี **แหล่ง backend มากกว่า 1 ตัว** หรือ origin ดับเป็นช่วง; ถ้าเจออาการถี่ ให้เช็ค Coolify (container ตัวเดียว) และ Cloudflare Load Balancing/DNS

## 10. Polling แบบ hybrid + scoped rate limit — ตรวจบน production จริง (2026-11-04)

Deploy commit `b65d9a3` (ต่อจาก `85b273f`) แล้วตรวจกับ `https://sams.scphtrang.ac.th` ด้วย UA `sams-probe/1.0` และบัญชีทดสอบอาจารย์ `teach2`

### ยืนยันว่าโค้ดใหม่ขึ้น production

| หลักฐาน | ผล |
|---|---|
| `GET /api/v1/health/` | 200 `database: "connected"` |
| `GET /api/v1/schema/` | พบ `AttendanceSession.check_in_effective_end` (readOnly, date-time) และ `SessionRoster.record_id` (readOnly, nullable) |
| JS chunk ของหน้า control room (`/_next/static/chunks/3w9-3osg96rd1.js`) | พบ `check_in_effective_end`, `record_id`, `visibilitychange`, ค่า interval 5000/25000/15000 และโค้ดจัดการ 429 |

### ผลทดสอบ API (คาบจริงบน production)

- `check_in_effective_end` ของคาบที่สร้างจริง = `check_in_end + 900 วินาที` (late 15 นาที, grace ของ production = 0) เช่น `20:43:51 → 20:58:51`
- roster คืน `record_id` ตรงกับ PK ของ record จริง (`2fc3a346-…`)
- PATCH `/attendance/records/{record_id}/` สำเร็จ 200 → roster รอบถัดไปแสดง `late`
- ระหว่าง poll ไม่มี `GET /attendance/records/` เลย (0 ครั้งตลอดการทดสอบ)

### ผลทดสอบ frontend บน production (Playwright 1366×900)

| สถานการณ์ | ผลที่วัดได้ |
|---|---|
| open + อยู่ในหน้าต่าง (17 วิ) | request roster ที่ 0 / 5.2 / 10.4 วิ → cadence ~5 วิ |
| open + อยู่นอกหน้าต่าง (70 วิ) | 0 / 25.0 / 50.5 วิ → cadence ~25 วิ |
| paused (วัดหลังกดหยุด 2.5 วิ นาน 18 วิ) | 1 ครั้งที่ 15.0 วิ → cadence 15 วิ |
| tab hidden 8 วิ | 0 request |
| กลับมา visible | ยิงทันที 1 ครั้ง แล้วกลับเข้า cadence ปกติ |
| closed (9 วิ) | 0 request |
| บังคับ 429 ที่ browser (intercept เฉพาะ roster) | banner "ระบบจำกัดจำนวนคำขอชั่วคราว…" ขึ้น, ยิงซ้ำหลัง ~10 วิ, banner หายเองหลัง poll สำเร็จ |

### Rate limit จริงที่ backend

- ยิง roster 240 ครั้งใน 36.3 วิ → `200: 160`, `429: 80`
- 429 มี header `retry-after` และ body `{"code":"THROTTLED","data":{"wait_seconds":…}}`
- ขณะ roster ติด 429: `GET /attendance/sessions/` และ `GET /attendance/records/` ยัง 200 → ยืนยันว่า polling ใช้ bucket แยก ไม่กิน global `user` (600/hour)

**ข้อจำกัดที่พบ (ยังไม่แก้รอบนี้):** production ยังไม่มี `CACHES` ที่ใช้ร่วมกัน ทำให้ DRF throttle นับใน LocMem ของแต่ละ gunicorn worker (3 workers) — ค่า `60/min` จึงมีผลระดับ worker ไม่ใช่ทั้งระบบ (observed ~160 คำขอก่อนเริ่ม 429) แผน Phase 3 คือ Redis; ระหว่างนี้ 1800/hour + 60/min ยังกันการยิงถี่ผิดปกติได้ในระดับ worker และ frontend backoff 10→20→40→60 วิ ช่วยลดภาระจริง

### เก็บกวาดข้อมูลทดสอบ

ลบคาบทดสอบ 3 คาบ (session + record + QR token 16 รายการ) และ enrollment ชั่วคราว 1 แถวออกจาก production แล้ว — `teach2` กลับมามี 0 คาบเหมือนก่อนทดสอบ; audit log ของการทดสอบยังอยู่ตามข้อจำกัด append-only ของระบบ

### ข้อสังเกตอื่น

- เจอ Cloudflare `520` 1 ครั้งจากการยิง concurrent 80 คำขอ — หลังลด concurrency ไม่เกิดซ้ำ
- พบ 401 จาก `/api/v1/auth/refresh/` 2 ครั้งระหว่างเปิดหน้า (refresh token เก่า/ถูก rotate) แต่หน้าโหลดต่อได้ปกติ — เป็น race เดิม ไม่ใช่ผลจากงานนี้

## 11. Instructors: หลักสูตร/สาขา dropdown + ลบพร้อมบัญชีผู้ใช้ (2026-11-05)

### หลักสูตร/สาขาเป็น dropdown (commit `9549cc3`)

- Playwright local (1366×900): `#instr-department` แสดง `— ไม่ระบุ —`, `CS-2569 · วิทยาการคอมพิวเตอร์ (ปริญญาตรี)`, `SAN · สาธารณสุข` และ **ไม่มี** `required`
- สร้างอาจารย์ด้วยตัวเลือก CS-2569 → แถวใหม่แสดง `วิทยาการคอมพิวเตอร์ (ปริญญาตรี)` ถูกต้อง
- แก้ไขอาจารย์เดิมที่มีค่าแบบข้อความอิสระ (T0001 "ภาควิชาวิทยาการคอมพิวเตอร์") → ตัวเลือก "(ค่าเดิม)" ถูกเลือกและค่ายังอยู่หลังบันทึก
- `tsc --noEmit`, `eslint`, `npm run build` ผ่าน; backend 73/73
- ลบรายการ/บัญชีทดสอบออกจาก DB local แล้ว

### การลบอาจารย์ลบบัญชีผู้ใช้ไปด้วย

`DELETE /api/v1/instructors/{id}/` ลบ `User` (และ `InstructorProfile` แบบ CASCADE) ภายใน `transaction.atomic()`; ถ้าโดน `PROTECT` (คาบเช็คชื่อ / รายวิชาที่เปิดสอน / audit log) จะระงับบัญชีแทน

| กรณี | ผลทดสอบจริง |
|---|---|
| อาจารย์ใหม่ไม่มี references (backend test) | ✅ 204, `User` และ `InstructorProfile` หายจาก DB |
| อาจารย์ที่มี course offering (backend test) | ✅ 200 ข้อความ "บัญชีอาจารย์ถูกอ้างอิงโดยประวัติการใช้งาน — ระงับบัญชีแทนการลบ", `is_active=False`, profile status `inactive`, offering ยังอยู่ |
| instructor เรียก DELETE เอง | ✅ 403 |
| Playwright: สร้างผ่าน UI แล้วลบ | ✅ dialog ระบุ `ระบบจะลบบัญชีผู้ใช้ "probe_del_ui" ไปพร้อมกัน`, ปุ่ม "ลบทั้งอาจารย์และบัญชี", toast "ลบข้อมูลอาจารย์และบัญชีผู้ใช้สำเร็จ", แถวหาย และตรวจ DB แล้วทั้ง user/profile = 0 |
| Playwright: ลบอาจารย์ที่มี offering | ✅ toast แสดงข้อความระงับบัญชีแทน, แถวยังอยู่สถานะ "ไม่ใช้งาน", DB: `is_active=False` + profile `inactive` |
| Backend suite | ✅ 76/76 (เพิ่ม 3 tests ใน `InstructorDeleteTests`) |

ข้อมูลทดสอบ local (`DELUI01`, `SOFTUI`) ถูกลบออกจาก DB หลังทดสอบแล้ว

## 12. Enrollments: ถอน/ลบ/ลงทะเบียนใหม่ + ตัวกรองภาคการศึกษา + Batch (2026-11-05 – 2026-11-06)

แก้ปัญหาการลงทะเบียนรายวิชาที่สอนไปแล้ว/ลงผิดพลาด โดยแยก **ถอน** (เก็บประวัติ) ออกจาก **ลบ** (เฉพาะแถวที่ยังไม่มีประวัติ) — backend บังคับกฎเดียวกัน ไม่ใช่แค่ซ่อนปุ่มบน UI — และเพิ่ม **เลือกหลายรายการ + Batch process** ที่ประมวลผลทีละแถว

### Backend (`apps.courses`)

| กรณีทดสอบ | ผล |
|---|---|
| ถอนขณะมีประวัติเช็คชื่อ | ✅ 200, สถานะ `dropped`, `AttendanceRecord` ยังอยู่, list คืน `attendance_record_count=1` |
| ลบแถวที่มีประวัติ | ✅ **409 `HAS_ATTENDANCE`** และแถวยังอยู่ |
| ลบแถวที่ยังไม่มีประวัติ | ✅ 204 และแถวหายจาก DB |
| ลงทะเบียนใหม่ (reinstate) | ✅ 200 กลับเป็น `enrolled` |
| เพิ่มการลงทะเบียนใน offering `completed` | ✅ 400 |
| ลงทะเบียนใหม่ใน offering `completed` | ✅ 400 `OFFERING_CLOSED` |
| แก้ไขสถานะเป็น `enrolled` ผ่าน PATCH ใน offering ที่จบแล้ว | ✅ 400 (ไม่ให้เลี่ยงกฎด้วยฟอร์มแก้ไข) |
| เปลี่ยนนักศึกษาเมื่อมีประวัติเช็คชื่อ | ✅ 400 |
| instructor ถอนรายการของอาจารย์อื่น | ✅ 403/404 และสถานะไม่เปลี่ยน |
| ตัวกรอง `?academic_term=` (UUID / ค่าไม่ถูกต้อง) | ✅ กรองถูก / คืน list ว่าง |
| bulk enroll มีแถวที่ถอนอยู่ | ✅ `created=0, skipped=0, dropped=1` และไม่ปรับสถานะกลับเป็น enrolled เอง |
| bulk enroll ใน offering `completed` | ✅ 400 `OFFERING_CLOSED` |
| **batch withdraw** 2 แถว (แถวปกติ + แถวถอนอยู่แล้ว) | ✅ 200, `succeeded=1, skipped=1, failed=0`; ประวัติยังอยู่ครบ |
| **batch withdraw** ไม่ส่ง `reason` | ✅ 400 `REASON_REQUIRED` และไม่มีแถวใดถูกเปลี่ยนสถานะ |
| **batch withdraw** มีแถว `completed` ปน | ✅ 200, `succeeded=1, failed=1` (`INVALID_STATUS`) — แถวดีถูกถอน แถวที่จบแล้วไม่เปลี่ยน |
| **batch delete** แถวมีประวัติ + ไม่มีประวัติ | ✅ 200, `succeeded=1, failed=1` (`HAS_ATTENDANCE`); แถวที่มีประวัติยังอยู่ |
| **batch delete** instructor แตะแถวของอาจารย์อื่น | ✅ 200, แถวของตัวเองถูกลบ, แถวนอก scope ได้ `NOT_FOUND` และไม่ถูกลบ |
| **batch** ส่ง `ids` ว่าง / ไม่ใช่ UUID | ✅ 400 `INVALID_IDS` |

### UI (in-app Chromium, localhost:3000, 1366×900)

ทดสอบกับนักศึกษาชั่วคราว `TST9001` (มี AttendanceRecord 1 ครั้ง) และ `TST9002` (ไม่มีประวัติ) ใน offering 30110003

| สถานการณ์ | ผลที่ยืนยัน |
|---|---|
| เปิด `/admin/enrollments` | ✅ แบนเนอร์อธิบายกฎ, คอลัมน์ "ประวัติเช็คชื่อ", ตัวกรอง "ภาคการศึกษา" แสดงครบ |
| กด **ถอน** TST9001 | ✅ SweetAlert บังคับกรอกเหตุผล, `POST …/withdraw/` 200, toast "ถอนการลงทะเบียนสำเร็จ — ประวัติการเช็คชื่อยังอยู่ครบ", แถวเป็น "ถอนรายวิชา", ประวัติยังแสดง 1 ครั้ง, ปุ่มเปลี่ยนเป็น "ลงทะเบียนใหม่" |
| กด **ลบ** แถวเดิม (มีประวัติ) | ✅ dialog "ลบการลงทะเบียนไม่ได้ — มีประวัติเช็คชื่อ 1 ครั้ง…" และ **ไม่มี DELETE request** |
| กด **ลงทะเบียนใหม่** | ✅ `POST …/reinstate/` 200, toast สำเร็จ, กลับเป็น "กำลังศึกษา" และประวัติยัง 1 ครั้ง |
| กด **ลบ** TST9002 (ไม่มีประวัติ) | ✅ dialog เตือนลบถาวร, `DELETE` **204**, แถวหายจากตาราง |
| เลือกภาคการศึกษา 2569/2 | ✅ request มี `academic_term=<uuid>` และเหลือเฉพาะรายการของภาคนั้น (AI) |

### Batch (multiselect) — UI

ทดสอบฝั่ง instructor (`teach1`) บน `/instructor/enrollments` กับ offering SC222 และนักศึกษาชั่วคราว `BATCH01`–`BATCH04`:

| สถานการณ์ | ผลที่ยืนยัน |
|---|---|
| ติ๊กเลือก 3 แถว | ✅ แถบ "เลือกแล้ว 3 รายการ" + ปุ่ม "ถอนที่เลือก (3)" / "ลบที่เลือก (3)" แสดง; แถวที่เลือกมีพื้นหลังต่าง |
| ติ๊ก "เลือกทั้งหมดในหน้านี้" | ✅ เลือกครบ 5 แถว; เมื่อปลด 1 แถว checkbox หัวตารางเป็น `indeterminate` และนับ 4 |
| **ลบที่เลือก** 3 แถว (1 มีประวัติ + 2 ไม่มี) | ✅ dialog เตือน "มี 1 รายการที่มีประวัติ…จะไม่ถูกลบ"; `POST …/batch-delete/` 200; สรุป "สำเร็จ 2 · ข้าม 0 · ไม่สำเร็จ 1" พร้อมรายละเอียด `BATCH01 — มีประวัติเช็คชื่อ 1 ครั้ง`; ตารางเหลือ 5 แถว และ BATCH03/BATCH04 หายไป |
| **ถอนที่เลือก** 2 แถว (1 กำลังศึกษา + 1 ถอนอยู่แล้ว) | ✅ SweetAlert บังคับเหตุผลและแจ้ง "1 รายการที่ถอนอยู่แล้วจะถูกข้าม"; `POST …/batch-withdraw/` 200; สรุป "สำเร็จ 1 · ข้าม 1 · ไม่สำเร็จ 0" พร้อมรายละเอียดแถวที่ข้าม |
| หลังถอน | ✅ `BATCH01` เป็น "ถอนรายวิชา" และคอลัมน์ประวัติยังแสดง **1 ครั้ง**; `BATCH02` คงสถานะเดิม; selection ถูกล้างหลังปิดสรุป |
| เปลี่ยนหน้า/คำค้น/ตัวกรอง | ✅ selection ถูกล้าง (ไม่ส่ง id ที่มองไม่เห็นเข้า batch) |

### ตรวจสอบเพิ่มเติม

- ตรวจ DB หลัง UI batch: `BATCH01` = `dropped` + AttendanceRecord 1 แถว, `BATCH02` = `dropped`; `BATCH03`/`BATCH04` ไม่มี enrollment; audit log มี `enrollment_withdraw` (`reason`, `batch: true`, `batch_size: 2`) และ `enrollment_delete` (`batch: true`, `batch_size: 3`)
- ตรวจ DB หลัง UI ก่อนหน้า: TST9001 = `enrolled` + record 1 แถว; TST9002 ไม่มี enrollment; audit log มี `enrollment_withdraw` (พร้อม reason), `enrollment_reinstate`, `enrollment_delete`
- เก็บกวาดข้อมูลทดสอบ local แล้ว (`TST9001`/`TST9002` และ `BATCH01`–`BATCH04` + record + session + enrollment + user = 0 ทั้งหมด)
- Backend suite: ✅ **94/94** (SQLite, `DEBUG=True`)
- `npx tsc --noEmit` และ `npx eslint` ผ่าน 0 error

## 13. Dropdown รายวิชาที่เปิดสอน: รหัสวิชา · ชื่อรายวิชา + เฉพาะสถานะที่ยังเปิด (2026-11-07)

dropdown เลือก "รายวิชาที่เปิดสอน" ที่ใช้ **สร้าง/ผูก** ข้อมูลใหม่ และ **ตัวกรอง** ในหน้าเหล่านั้น แสดง `รหัสวิชา · ชื่อรายวิชา` (เดิม `รหัสวิชา · ภาคการศึกษา`) และดึงเฉพาะ offering สถานะ `open`/`in_progress` — รายวิชาที่ "จบภาคเรียนแล้ว" หรือ "ยกเลิก" จะไม่ถูกเลือกได้อีก: หน้า คาบเช็คชื่อ, ตารางเรียน (admin/instructor `/schedules`) และ การลงทะเบียน (ฟอร์มรายคน + ลงทะเบียนกลุ่ม + ตัวกรอง) · instructor ยังเห็นเฉพาะรายวิชาที่ตนสอนดังเดิม · หน้า **Reports** ตั้งใจเก็บรายการทุก offering เพื่อกรองรายงานรายวิชาที่จบไปแล้ว (label เปลี่ยนเป็นรูปแบบใหม่ด้วย)

### UI (in-app Chromium, localhost:3000)

ทดสอบกับข้อมูลจริงใน DB local: offering 30110001–30110003 (`open`), SC222 (`open`), AI (`cancelled` — ต้องไม่ปรากฏใน dropdown)

| จุดที่ทดสอบ | ผลที่ยืนยัน |
|---|---|
| `/instructor/enrollments` ฟอร์มเพิ่มรายคน | ✅ เหลือ `SC222 · สถิติเพื่อการสร้างเสริมสุขภาพ` เท่านั้น (AI หายไป) |
| `/instructor/enrollments` ฟอร์มลงทะเบียนกลุ่ม | ✅ เหลือ SC222 เท่านั้น |
| ตัวกรอง "รายวิชาที่เปิดสอน" บนหน้า enrollments | ✅ เหลือ SC222 เท่านั้น |
| `/instructor/attendance` ฟอร์มสร้างคาบ | ✅ เหลือ SC222 เท่านั้น |
| `/instructor/schedules` ตัวกรอง + ฟอร์มสร้างตารางเรียน | ✅ แสดงเฉพาะวิชาที่ยังเปิด, แบบ รหัส · ชื่อ |
| `/admin/attendance-sessions` ฟอร์มสร้างคาบ + ตัวกรอง | ✅ เห็น 30110001-3 · SC222 (4 วิชาที่ `open`), ไม่มี AI |
| `/admin/reports` ตัวกรองรายวิชา | ✅ ยังเห็นทุก offering รวม AI (ตามเจตนา), เปลี่ยน label เป็น รหัส · ชื่อ |

### ตรวจสอบเพิ่มเติม

- `npx tsc --noEmit` และ `npx eslint` ผ่าน 0 error
- ไม่มีการเปลี่ยน backend/model → ไม่มี migration
- ข้อมูลที่ใช้ทดสอบเป็นข้อมูลจริงใน DB local (ตัวอย่าง offering ที่สร้างไว้ก่อนหน้า) — ไม่ได้สร้างข้อมูลทดสอบชั่วคราว

## 14. บันทึกพิกัดอุปกรณ์ตอนสแกน (evidence ไม่บังคับ — fail-open) (2026-11-07)

ตอนนักศึกษากดเช็คชื่อหน้า `/student/scan` หน้าจะขอตำแหน่งอุปกรณ์ (Geolocation API, timeout 8 วิ) แล้วส่งไปพร้อม token — **เป็นข้อมูลหลักฐานเท่านั้น ไม่ถูกใช้ตัดสินสิทธิ์เช็คชื่อ**: ผู้ใช้ปฏิเสธ / หาตำแหน่งไม่ได้ / อุปกรณ์ไม่รองรับ → ส่ง `location_status` แทน และเช็คชื่อยังสำเร็จเหมือนเดิม ฝั่ง server บันทึกลง `attendance_records` คอลัมน์ใหม่: `latitude`, `longitude`, `location_accuracy_m`, `location_status` (`granted`/`denied`/`unavailable`/`unsupported`/ว่างเมื่อบันทึกโดยอาจารย์), `client_ip` (ตัวแรกของ `X-Forwarded-For` → `X-Real-IP` → `REMOTE_ADDR`) · server สร้างสถานะ `granted` เองจากพิกัดจริงเท่านั้น (client ประกาศเองไม่ได้ → 400) · นักศึกษาไม่เห็น IP ของตัวเองใน history (staff เท่านั้น) · หน้า `/admin/attendance-records` เพิ่มคอลัมน์ "พิกัดตอนสแกน"

### Backend tests

- รวม suite: ✅ **100/100** (SQLite, `DEBUG=True`) — เพิ่ม 6 tests: พิกัดถูกบันทึก + IP, X-Forwarded-For ชนะ REMOTE_ADDR, ไม่ส่งพิกัด → `unavailable`, `denied` → ยังสำเร็จ, client ประกาศ `granted` เอง → 400, IP ซ่อนจากนักศึกษาแต่ admin เห็น
- Migration: `attendance.0002_attendancerecord_client_ip_attendancerecord_latitude_and_more` (ใช้แล้วบน SQLite dev; **prod ต้องรัน migrate ตอน deploy**)

### UI (in-app Chromium, localhost:3000) — flow `/student/scan` กรอก token ด้วยมือ (code path เดียวกับการสแกน)

| สถานการณ์ | ผลที่ยืนยัน |
|---|---|
| เบราว์เซอร์ปฏิเสธตำแหน่ง (จริงจาก environment) | ✅ ขึ้น "กำลังขอตำแหน่งอุปกรณ์… (ไม่ยินยอมกดเช็คชื่อได้อยู่)" → เช็คชื่อ **200 สำเร็จ**; DB: `location_status='denied'`, ไม่มีพิกัด, `client_ip=127.0.0.1` |
| ผู้ใช้อนุญาต + มีพิกัด (จำลองสิทธิ์ Allow + พิกัดจริงจากจอ) | ✅ เช็คชื่อ **200 สำเร็จ**; DB: `lat=13.736717, lng=100.523186, accuracy=12.5, location_status='granted', client_ip=127.0.0.1` |
| หน้า `/admin/attendance-records` (sadmin) | ✅ คอลัมน์ "พิกัดตอนสแกน" แสดง `13.73672, 100.52319 ±12.5 ม.` สำหรับแถวมีพิกัด, `-` สำหรับแถวเก่า |
| ไม่ส่งตำแหน่งเลย (client เก่า) | ✅ (unit test) เช็คชื่อสำเร็จ, record `unavailable` — ยืนยันว่า process ทำงานแบบไม่บังคับเต็ม 100% |

### บั๊กที่จับได้และแก้แล้วในรอบนี้

- DRF คืน `DecimalField` เป็น string ทำให้หน้า Records โหลดไม่ขึ้น (`r.latitude.toFixed is not a function`) → แก้ serializer ส่ง `FloatField` (ตัวเลข) — ยืนยันหน้าโหลดและแสดงผลถูกต้องหลังแก้

### ข้อจำกัดที่บันทึกไว้

- **การสแกนผ่านกล้องจริง** ไม่ได้ทดสอบในรอบนี้ (automation ของเราไม่มีกล้อง/QR จริง) — ทดสอบผ่านช่องกรอก token ด้วยมือ ซึ่งใช้ `submitToken` code path เดียวกัน (ขอพิกัด + POST)
- ชี้แจงพฤติกรรม token TTL รอบทดสอบ: dev server รอบนี้ตั้ง `ATTENDANCE_QR_TTL_SECONDS=600` เพื่อสะดวกในการทดสอบ (prod ยังใช้ 30 วิ ตาม default) — ผลเช็คชื่อไม่ขึ้นกับ TTL
- เก็บกวาดข้อมูลทดสอบ local แล้ว: session ทดสอบ + QR tokens + records + enrollment `student01`→SC222 ถูกลบหมด (คาบเดิม `65de7cae…` ของ offering 30110001 คงสถานะเดิม)

