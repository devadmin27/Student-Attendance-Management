# SAMS — Student Attendance Management System

ระบบบริหารจัดการการเข้าเรียนผ่าน QR Code (Monorepo)

- `backend/` — Django 6.1.2 + Django REST Framework 3.18.3 (API ที่ `/api/v1/`)
- `frontend/` — Next.js 16.4.3 + React 19 + Tailwind 4 (ภาษาไทย, 3 roles)
- ฐานข้อมูลผลิต: **Supabase PostgreSQL** — SQLite ใช้เฉพาะ dev เมื่อ `DJANGO_DEBUG=True`

## ฟีเจอร์หลัก

- **QR Attendance**: คาบเช็คชื่อ (session) มี lifecycle `open → paused → closed/cancelled`; token หมุนทุก 30 วินาที (TTL), เซิร์ฟเวอร์เก็บเฉพาะ **SHA-256 hash**; duplicate check-in ถูกกันที่ระดับ unique constraint และตอบ **409 `ATTENDANCE_ALREADY_EXISTS`**
- **RBAC 3 บทบาท**: Admin / Instructor / Student พร้อม dashboard ต่างกันทั้ง 3 แบบ
- **JWT**: access token อายุสั้น (default 10 นาที) + refresh rotation + blacklist; refresh token อยู่ใน **HttpOnly cookie** (`sams_refresh`) — ไม่เก็บ token ใน localStorage
- **Audit logs**: บันทึกการกระทำสำคัญ (แก้ attendance record ต้องระบุ `edit_reason`, ระบุผู้แก้)
- **CSV**: import/export sanitize formula injection (=HYPERLINK เป็นต้น), export เป็น UTF-8-BOM เพื่อ Excel อ่านภาษาไทยถูกต้อง
- **API Documentation**: OpenAPI + Swagger UI ที่ `/api/v1/docs/`

## Quickstart (Development)

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # บน Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env            # กรอกค่าจริง (หรือใช้ SQLite + DEBUG=True สำหรับ dev)
python manage.py migrate
python manage.py create_admin --username admin --password <your-password>
python manage.py runserver        # http://localhost:8000  (API ที่ /api/v1/)
```

> Dev แบบง่าย: ตั้ง `DB_ENGINE=sqlite` + `DJANGO_DEBUG=True` (backend บังคับห้ามใช้ SQLite เมื่อ DEBUG=False)

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:3000
```

## เอกสาร

| เอกสาร | เนื้อหา |
|---|---|
| [`docs/SAMS.md`](docs/SAMS.md) | ข้อกำหนดต้นฉบับ (spec) ฉบับเต็ม |
| [`docs/architecture.md`](docs/architecture.md) | โครงสร้าง monorepo, envelope, JWT flow, QR rotation |
| [`docs/api-documentation.md`](docs/api-documentation.md) | endpoints, envelope, error codes, RBAC |
| [`docs/database-schema.md`](docs/database-schema.md) | schema จริง 25 ตาราง (generate จาก Postgres) |
| [`docs/installation.md`](docs/installation.md) | ติดตั้งทีละขั้น (dev + production) |
| [`docs/deployment.md`](docs/deployment.md) | deploy จริง: Supabase + HTTPS + JWT cookies |
| [`docs/user-manual.md`](docs/user-manual.md) | คู่มือใช้งานสำหรับ Admin / Instructor / Student |
| [`docs/test-report.md`](docs/test-report.md) | ผลทดสอบจริงทั้งหมด (API + UI + Postgres) |
| [`docs/security-review.md`](docs/security-review.md) | ทบทวนด้านความปลอดภัย |

## Security notes

- สภาพแวดล้อมจริงที่ deploy ทดสอบ: server PostgreSQL ไม่รองรับ SSL บนพอร์ต 5432 จึงตั้ง `DB_SSLMODE=disable` — ดูรายละเอียดและข้อแนะนำใน [`docs/security-review.md`](docs/security-review.md)
- ห้าม commit `.env`, `db.sqlite3`, ไฟล์ build หรือ artifacts ใด ๆ (ดู `.gitignore`)
- รหัสผ่านบัญชี admin ผลิตที่ seed ด้วย `create_admin` ควรเปลี่ยนหลังใช้งานจริง
