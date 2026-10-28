# SAMS — Security Review

ทบทวนด้านความปลอดภัยตามสิ่งที่ implement และ **ยืนยันจริง** ระหว่าง dev · อ้างอิง spec SAMS.md §15 (security), §16 (audit), §10 (QR)

## 1. Authentication & Tokens

| มาตรการ | รายละเอียด (ตามที่ implement จริง) | สถานะ |
|---|---|---|
| Access token อายุสั้น | default 10 นาที (validate 1–240), settings.py raise ถ้าค่านอก range | ✅ ทดสอบจริง |
| Refresh rotation + blacklist | `ROTATE_REFRESH_TOKENS=True`, `BLACKLIST_AFTER_ROTATION=True` (SimpleJWT token_blacklist app) | ✅ ทดสอบจริง |
| Refresh ใน HttpOnly cookie | ชื่อ `sams_refresh`, path=`/api/v1/auth/`, SameSite=Lax, `Secure` เมื่อ DEBUG=False — **ไม่เก็บใน localStorage** | ✅ ทดสอบจริง (Chromium localhost) |
| Access token ใน browser | memory เท่านั้น (`setAccessToken`) — ไม่เขียน storage | ✅ ตามโค้ด `frontend/lib/api.ts` |
| Single-flight refresh | 401 → refresh กันไม่ให้เรียกซ้อน — ยืนยัน reload ×2 ไม่ rotate ซ้ำ | ✅ ทดสอบจริง |
| ความยาวรหัสผ่าน + validators | min 8 + numeric + common + user-similarity (Django) | ✅ มีใน settings |
| Brute-force | throttle `login: 10/min` บน endpoint login | ⚠️ ตั้งไว้ที่ settings (ยังไม่ทดสอบ rate ขอบจริง) |

## 2. QR Attendance

- Token TTL 30 วินาที (validate 5–3600) — ทดสอบจริง: issue id กลับมา `ttl=29s`
- **เซิร์ฟเวอร์เก็บเฉพาะ SHA-256 hash** — leak ฐานข้อมูลไม่เปิดเผย token ดิบ (ดู QR security ของ spec §10.2)
- Duplicate: unique constraint `(session, student)` + ตอบ 409 `ATTENDANCE_ALREADY_EXISTS` — ทดสอบ race จริง 2 threads ผ่านบน Postgres ผลิต
- Replay ตาม token เดิม/หมดอายุ — token ที่หมดอายุถูกบล็อกด้วย hash + TTL ตอน validate

## 3. RBAC

- default `IsAuthenticated` ทุก view ยกเว้น health/docs/login
- Audit logs: admin เท่านั้น — instructor/student ได้ 403 (ทดสอบจริง)
- Instructor ควบคุมได้เฉพาะคาบของตัวเอง (SessionScopeMixin — consistent list + detail + actions)
- Student เห็น attendance/records ของตัวเองเท่านั้น (my-history + roster-adjacent)

## 4. CSV Injection & Export

- **Import** — ทุก field sanitize ด้วย `common/csvutils.sanitize_csv_value`: เห็น values ที่ขึ้นต้น `=`, `+`, `-`, `@` (เช่น `=HYPERLINK`, `+HYPERLINK`) ถูกแปลงเป็นข้อความเป็นต้น (`'ฉ้อฉล(ถูกแก้)`) — ทดสอบจริงด้วย smoke scripts (`smoke_csv_import.py`, `verify_smoke.py`)
- **Export** — UTF-8-BOM เพื่อ Excel อ่านภาษาไทยถูกต้อง — bytes เริ่มด้วย `EF BB BF` (ยืนยันจริง)
- ขนาดอัปโหลดจำกัด 2 MB (`DATA_UPLOAD_MAX_MEMORY_SIZE`), throttle import `5/hour`

## 5. Audit & Logging

- แก้ attendance record ต้องมี `edit_reason` + ระบบบันทึก `edited_by` (username อาจารย์) อัตโนมัติ → ตอบแสดงใน audit logs (ทดสอบจริง)
- Logging ตั้งไฟล์ `backend/logs/sams.log` เมื่อ DEBUG=False — ห้าม log token/รหัสผ่านค่าเต็ม
- Audit logs API admin-only, แสดงเป็น list pagination 20/หน้า (ทดสอบจริง)

## 6. HTTP / Browser hardening (เปิดเมื่อ DEBUG=False)

| มาตรการ | ค่า |
|---|---|
| HSTS | 30 วัน default, includeSubDomains, preload |
| SECURE_PROXY_SSL_HEADER | `X-Forwarded-Proto https` |
| SESSION/CSRF cookie Secure | เปิด |
| X-Frame-Options | DENY |
| XSS filter / nosniff | เปิด |
| CORS | allow credentials จาก explicit origins เท่านั้น |

## 7. สถานะสิ่งที่ยังไม่ได้ทดสอบจริง (ต้องแจ้งตรงไปตรงมา)

รายการเหล่านี้ implement ตามโค้ดและตั้งค่าไว้แล้ว แต่ **ไม่ได้พิสูจน์พฤติกรรมผ่านการโจมตีจริง**

- Throttle ที่ขอบ (เรียกเกิน 10 login/rate จริงเพื่อเห็น 429)
- CSRF ของ cookie refresh บน cross-site attack (มี SameSite=Lax + path จำกัดอยู่แล้ว แต่ไม่รัน exploit)
- Rotated-token reuse หลัง logout (มี blacklist app + logout set cookie หมดอายุ แต่ยังไม่รันตรวจ token เก่าหลัง logout แบบเจาะจง)

## 8. ข้อสังเกตสภาพแวดล้อมผลิต (พบจริง)

⚠️ **DB ผลิตไม่รองรับ SSL เชื่อมต่อบนพอร์ต 5432** (`209.15.111.118`) — ทดสอบจริงยืนยัน จึงต้องตั้ง `DB_SSLMODE=disable` ใน backend/.env

**ผลจริง:** traffic ระหว่าง Django ↔ Postgres เป็นแบบไม่เข้ารหัส

**Mitigation ที่แนะนำ (เลือกอย่างน้อยหนึ่งอย่าง):**
1. จำกัด IP source ที่เข้าถึงพอร์ต 5432 ทาง firewall/security group ให้เหลือเฉพาะ host ของ backend
2. พิจารณาใช้ **Supabase pooler / pgbouncer endpoint** ที่รองรับ SSL (พอร์ต 6543 หรือ equivalent ของ provider) แล้วตั้ง `DB_SSLMODE=require`
3. ระบบ backend และ DB ให้อยู่ใน private network/VPC ถ้าทรัพยากรอนุญาต

- **จำเป็น:** ห้าม commit `backend/.env` (มี credential จริงของ Supabase) — กันไว้แล้วใน `.gitignore`
