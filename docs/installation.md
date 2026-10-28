# SAMS — Installation Guide

## ความต้องการระบบ

- Python 3.13+ (ทดสอบจริงด้วย venv ใน `backend/.venv`)
- Node.js 22+ / npm
- PostgreSQL (production: Supabase) — dev ใช้ SQLite ได้ **เฉพาะ `DJANGO_DEBUG=True`**

## 1. Backend (Django)

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt   # Django 6.1.2, DRF 3.18.3, SimpleJWT 5.5.1, drf-spectacular 0.30.0, django-filter 26.2, psycopg 3.3.6
```

ตั้งค่า environment — คัดลอก `backend/.env.example` เป็น `backend/.env` แล้วกรอกค่า:

| ตัวแปร | ค่าที่ใช้จริง |
|---|---|
| `DJANGO_SECRET_KEY` | **จำเป็น** เมื่อ DEBUG=False (startup จะ raise ถ้าไม่มี) |
| `DJANGO_DEBUG` | `True` เฉพาะ dev |
| `DB_ENGINE` | `postgresql` (production) หรือ `sqlite` (dev, ต้อง DEBUG=True) |
| `DB_HOST/PORT/NAME/USER/PASSWORD` | credential จริงของ Postgres (Supabase) |
| `DB_SSLMODE` | default `require` — ดูหมายเหตุใน deployment.md |
| `ATTENDANCE_QR_TTL_SECONDS` | default 30 (validate 5–3600) |

อ่านรายละเอียดทั้งหมด: `backend/.env.example`

Migrate + สร้าง admin:

```bash
python manage.py migrate
python manage.py create_admin --username admin --password <password>   # หรือทำผ่าน createsuperuser
python manage.py runserver
```

รันทดสอบ:

```bash
python manage.py test             # ทดสอบจริงผ่านครบ 50/50 ทั้งบน SQLite และ Supabase Postgres
```

## 2. Frontend (Next.js)

```bash
cd frontend
npm install
copy .env.example .env            # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api/v1
npm run dev                       # http://localhost:3000
```

Production build (ปิด dev server ก่อน — build ใช้โฟลเดอร์ `.next` เดียวกับ dev):

```bash
npm run lint                      # ทดสอบจริง: 0 ปัญหา
npm run build                     # ทดสอบจริง: 32/32 routes
npm start
```

## 3. ตรวจว่าติดตั้งสำเร็จ

1. `GET http://localhost:8000/api/v1/health/` → `{"success": true, "data": {"database": "connected", ...}}`
2. Login ผ่าน `http://localhost:3000/login` ด้วยบัญชี admin
3. Swagger UI: `http://localhost:8000/api/v1/docs/`

## 4. Docker (dev stack — ทางเลือก)

```bash
docker compose up
```

ดู `docker-compose.yml` ที่ root: backend (runserver) + frontend (next dev) ต่อกันผ่าน `NEXT_PUBLIC_API_BASE_URL` / `DJANGO_CORS_ALLOWED_ORIGINS`
