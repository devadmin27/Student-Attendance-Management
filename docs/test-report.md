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

## 7. ข้อสังเกตสภาพแวดล้อมผลิต

- Server Postgres ที่ใช้จริง **ไม่รองรับ SSL** บนพอร์ต 5432 → `DB_SSLMODE=disable` (บันทึกใน [`security-review.md`](security-review.md) พร้อม mitigation)
- ผลิต seed เฉพาะ `admin` — ควรเปลี่ยนรหัสผ่านหลังใช้จริง
