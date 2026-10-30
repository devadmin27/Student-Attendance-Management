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
| 13 (แก้แล้ว push `38c5173` + `44672b2`) | รายงานจากผู้ใช้จริง: หน้า `/attendance` instructor กด "สร้างคาบเช็คชื่อ" → 500 ("เกิดข้อผิดพลาดในการเชื่อมต่อระบบ") | บัญชี instructor ที่ไม่มี InstructorProfile (สร้างผ่านหน้า Users ได้บัญชีเปล่า) — serializer/view เข้าถึง `user.instructor_profile` ตรง ๆ → `RelatedObjectDoesNotExist` → 500; และก่อนแก้ instructor ไม่มี profile **เห็น sessions/records ของทุกคน** (fallback ไป unscoped queryset) | แก้ 3 ชั้น: 400 `NO_INSTRUCTOR_PROFILE` ข้อความชัดทั้ง view + serializer; scoping ของ sessions + records **fail-closed** (queryset ว่างถ้าไม่มี profile) — ยืนยันจริงบน prod: bare instructor GET sessions/records → 200 ว่าง ✅;ส่วนผู้มี profile สร้าง session ได้ปกติ ✅ (deploy รอบ `38c5173`), view guard `44672b2` ยังรอ deploy รอบถัดไป |

### ข้อสังเกตด้านโครงสร้าง infra ผลิต

- มี **ช่วงเวลา** ที่ request รำวรายสลับ 503 "no available server" (Cloudflare) และ 401 `NOT_AUTHENTICATED` แบบไม่อธิบายได้ด้วย app-token — หายเองในหลายนาที. สันนิษฐานว่ามี **แหล่ง backend มากกว่า 1 ตัว** หรือ origin ดับเป็นช่วง; ถ้าเจออาการถี่ ให้เช็ค Coolify (container ตัวเดียว) และ Cloudflare Load Balancing/DNS

