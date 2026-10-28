# SAMS — Deployment Guide

แนวทาง deploy จริงที่ใช้และยืนยันระหว่าง dev: **Supabase PostgreSQL + Django (prod server) + Next.js** โดยมี HTTPS อยู่หน้า reverse proxy

## 1. Checklist ฝั่ง Backend

`backend/.env` ฝั่งผลิตต้องมีค่าดังนี้ (settings.py ตรวจแบบ hard-check ที่ startup):

| ตัวแปร | ความหมาย / ข้อบังคับ |
|---|---|
| `DJANGO_DEBUG=False` | เปิด cookie Secure + HSTS + SECURE_PROXY_SSL_HEADER; **ห้ามใช้ SQLite** (settings จะ raise ทันที) |
| `DJANGO_SECRET_KEY` | จำเป็นเมื่อ DEBUG=False (startup จะ raise ถ้าไม่มี) — สุ่มยาว ≥ 64 ตัวอักษร |
| `DJANGO_ALLOWED_HOSTS` | โดเมนผลิต + localhost สำหรับ smoke ท้องถิ่น |
| `DJANGO_CORS_ALLOWED_ORIGINS` | origin ของ frontend ผลิต (`CORS_ALLOW_CREDENTIALS=True` ใช้เสมอ) |
| `DJANGO_SECURE_SSL_REDIRECT` | เปิด `True` เมื่อ proxy รองรับ (default False เพื่อ local smoke) |
| `DJANGO_HSTS_SECONDS` | default 30 วัน, includeSubDomains + preload |
| `DB_ENGINE=postgresql` | (SQLite ถูกปฏิเสธทันทีใน production) |
| `DB_HOST / DB_PORT / DB_NAME / DB_USER / DB_PASSWORD` | Supabase credential จริง (ห้าม commit) |
| `DB_SSLMODE` | default `require` — server จริงที่ใช้ไม่รองรับ SSL (ดู §5) |
| `ATTENDANCE_QR_TTL_SECONDS` | default 30 (validate 5–3600) |

## 2. Migrate + seed ผลิต

```bash
python manage.py migrate
# ผลจริงบน Supabase Postgres: 25 ตารางครบ (ยืนยันระหว่าง dev)
python manage.py create_admin --username admin \
  --password-env SAMS_ADMIN_PASSWORD   # ทางที่ปลอดภัย: รับรหัสผ่านจาก env (CI)
```

> Production seed **ไม่ใส่ข้อมูลจำลอง** — สร้างเฉพาะบัญชี `admin` ผลิต (ทดสอบจริง: `users_total=1` หลัง seed)
> **เปลี่ยนรหัสผ่าน admin หลังใช้งานจริงเสมอ**

## 3. HTTPS / Reverse Proxy

- ตั้ง reverse proxy (Nginx/Caddy) หน้าทั้ง backend และ frontend
- settings.py ตั้ง `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")` เมื่อ DEBUG=False — ยืนยันเปิดใช้แล้ว
- Refresh token cookie `sams_refresh` ออกพร้อม flag `Secure` เมื่อ DEBUG=False — ทดสอบจริงผ่าน Chromium บน `localhost` (browser ยอมรับ Secure cookie บน localhost) ทั้ง login/refresh และ reload ที่ session ยังค้าง

## 4. Backend process (ระดับผลิต)

ใช้ WSGI ที่ `config.wsgi.application` ผ่าน gunicorn หรือเทียบเท่า:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2
```

- Static files: `python manage.py collectstatic` → ให้ proxy เสิร์ฟจาก `backend/staticfiles/`
- CSRF_TRUSTED_ORIGINS ตั้งตาม CORS origins (settings ตั้งให้ตรงกันอัตโนมัติ)

## 5. ข้อจำกัดจริงที่พบ

Server PostgreSQL ที่ใช้จริง (`209.15.111.118:5432`) **ไม่รองรับ SSL** บนพอร์ตนี้ (ทดสอบจริง: การเชื่อมต่อด้วย `sslmode=require` ล้มเหลว) จึงต้องตั้ง `DB_SSLMODE=disable`

- เป็นข้อสังเกตด้านความปลอดภัย — จัดการด้วย: firewall จำกัด IP ที่เข้าถึง DB / พิจารณาใช้พอร์ต pooler ที่รองรับ SSL ของ Supabase / VPN
- รายละเอียดเพิ่มเติม: [`security-review.md`](security-review.md)

## 6. ทดสอบหลัง deploy (Production smoke ✅ ทดสอบจริง)

ลำดับที่ยืนยันระหว่าง dev บน Supabase stack:

1. `POST /api/v1/auth/login/` ด้วย admin ผลิต → access token + refresh cookie
2. `GET /api/v1/auth/me/` → envelope ครบ
3. `GET /api/v1/dashboard/admin/` → 17 keys, `users_total=1`
4. `POST /api/v1/auth/refresh/` (จาก browser) → rotate สำเร็จ
5. Reload หน้า `/admin/dashboard` ×2 → session ค้าง ไม่ถูก force-logout (single-flight refresh ทำงานถูกต้อง)
6. `python manage.py test` → **50/50 ผ่านบน Postgres ผลิต** (รวม race test duplicate records)

## 7. Frontend ผลิต

```bash
cd frontend
npm run lint        # 0 ปัญหา (ยืนยันจริง)
npm run build       # 32/32 routes (ยืนยันจริง)
npm start           # port 3000 — ให้ reverse proxy ชี้โดเมนมาที่ port นี้
```

> **ห้ามรัน `npm run build` ตอน `next dev` กำลังทำงาน** — พอร์ต/โฟลเดอร์ `.next` ชนกัน ทำให้ HMR พัง (พบจริงระหว่าง dev)
