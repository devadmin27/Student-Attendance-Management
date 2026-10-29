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

## 8. Deploy บน Coolify (Docker)

การเตรียมไฟล์ที่เกี่ยวข้อง (ทดสอบจริงในส่วนที่เครื่องพัฒนาทำได้ — ดูรายการท้ายหัวข้อ):

| ไฟล์ | หน้าที่ |
|---|---|
| `backend/requirements.txt` | เพิ่ม `gunicorn` (Web server ผลิต) + `whitenoise` (เสิร์ฟ static เมื่อ DEBUG=False) |
| `backend/config/settings.py` | เพิ่ม `whitenoise.middleware.WhiteNoiseMiddleware` หลัง SecurityMiddleware + `CompressedManifestStaticFilesStorage` เมื่อ DEBUG=False |
| `Dockerfile` (root ของโปรเจกต์) | อิมเมจผลิต Django backend — ตั้ง Build Context = repo root |

### ค่าที่ตั้งบน Coolify

- **Type:** Dockerfile, Dockerfile path: `/Dockerfile` (root), Build Context: `/`
- **Port:** `8000` (หรือกำหนด var `PORT` — สคริปต์ CMD อ่าน `${PORT:-8000}`)
- **Environment variables ที่ต้องใส่ (ไม่มีค่า default ที่เป็นจริงได้):**

| ตัวแปร | ค่า |
|---|---|
| `DJANGO_SECRET_KEY` | ค่าสุ่มยาว เฉพาะระบบ | 
| `DB_ENGINE` | `postgresql` (default อยู่แล้ว) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` | ครบชุดจาก Supabase (หรือ Postgres ภายใน Coolify) |
| `DB_PORT` | `5432` (default) |
| `DB_SSLMODE` | `require` สำหรับ Supabase โดยตรง; `disable` ถ้าผ่าน pooler/ตัวกรองที่ปฏิเสธ SSL (ทดสอบจริง: พอร์ต 5432 ของขบวนนี้ตอบ `N` ให้ SSL) |
| `DJANGO_ALLOWED_HOSTS` | โดเมนจริงที่ Coolify ผูกไว้ |
| `DJANGO_CORS_ALLOWED_ORIGINS` | URL จริงของ frontend เช่น `https://sams.example.ac.th` |

### สิ่งที่อิมเมจทำเองตอน deploy

1. `collectstatic` (ตอน build — ต้องใช้ dummy vars ภายใน Dockerfile แล้ว; **ไม่ต้องให้ค่าจริงตอน build**)
2. `migrate --noinput` ทุกครั้งที่สตาร์ท container
3. รัน `gunicorn config.wsgi:application` (3 workers, timeout 60s) — **ช่วย migrate ไม่ได้ถ้า DB ยังไม่พร้อม** ถ้า migrate พลาด container จะตาย → Coolify ต้องแสดง log จาก container ตัวนี้

### ข้อจำกัดที่ยืนยันทางทดสอบ

- ✅ `manage.py check` ผ่านด้วยอาวุธ whitenoise/gunicorn ติดตั้งแล้ว
- ✅ `collectstatic` รันด้วย env หน่วงตอน build สำเร็จ (157 files, 453 หลัง hashing เพิ่ม)
- ⚠️ **`gunicorn` รันบน Windows ไม่ได้** (ต้อง Linux) — ทดสอบ `docker build` บนเครื่องพัฒนาไม่ได้ (Docker Desktop ปิด) — ว่ากันไปตามเกณฑ์ "ห้ามประกาศพฤติกรรมที่ไม่ได้ทดสอบ": ผลจริงบน Coolify คือยังไม่ได้ยืนยันเช่นชนิดจนเครื่องมี daemon

### WhiteNoise กับ static

`CompressedManifestStaticFilesStorage` ให้บรอว์เซอร์ cache ตาม fingerprint hash — ต้องเรียก `{% static %}` ผ่าน template (Django admin ใช้แบบนี้อยู่แล้ว) และ manifest file (`staticfiles.json`) ถูก bake ลงอิมเมจแล้วเพราะ collectstatic รันด้วย `DEBUG=False` ตอน build

### Deploy frontend (Next.js) บน Coolify แยกอีก app หนึ่ง

| ไฟล์ | หน้าที่ |
|---|---|
| `frontend/Dockerfile` | อิมเมจผลิต Next.js แบบ **standalone** (multi-stage: deps → build → runner, node:22-slim) |
| `frontend/.dockerignore` | กัน `node_modules` / `.next` / `.env` ลง build context |
| `frontend/next.config.ts` | เปิด `output: "standalone"` |

ค่าที่ตั้งบน Coolify (app ใหม่, Dockerfile path `/frontend/Dockerfile`):

- **Domain:** โดเมนของ frontend เช่น `sams-app.scphtrang.ac.th`
- **Build args:** `NEXT_PUBLIC_API_BASE_URL=https://sams.scphtrang.ac.th/api/v1` (ค่า NEXT_PUBLIC_* ถูก bake ตอน build — **แก้แล้วต้อง Rebuild ไม่ใช่ restart**)
- **Port:** `3000` (CMD อ่าน `${PORT:-3000}`)

สิ่งที่ทดสอบจริงแล้ว:
- ✅ `npm run build` ผ่านครบทุก route (Next 16.4.3 + output standalone; ไฟล์ `server.js` ถูกสร้างจริงที่ `.next/standalone/`)
- ⚠️ ยังไม่ได้รัน `docker build` ในเครื่อง — ผลบน Coolify ต้องติดตาม log แล้วอ้างอิงส่วนท้าย §8

Backend env เมื่อ frontend ต่างโดเมน:
`DJANGO_CORS_ALLOWED_ORIGINS = https://sams.scphtrang.ac.th,https://sams-app.scphtrang.ac.th`

## 9. Deploy บน Coolify แบบ Docker Compose — โดเมนเดียวร่วมกัน

ตอบโจทย์: frontend + backend อยู่ **resource เดียว** กัน และใช้โดเมนร่วม `https://sams.scphtrang.ac.th`

### ไฟล์ที่เกี่ยวข้อง

| ไฟล์ | หน้าที่ |
|---|---|
| `docker-compose.production.yml` | 3 services: `proxy` (nginx), `backend` (Django, reuse Dockerfile ราก), `frontend` (Next.js, reuse frontend/Dockerfile) |
| `nginx/sams.conf` | กฎ route: `^/(api\|admin)\|static)/` → Django :8000 เส้นทางอื่น → Next.js :3000 |

### ตั้งบน Coolify

1. **New Resource → Docker Compose** ชี้ repo นี้ (branch `main`), Compose file path: `/docker-compose.production.yml`
2. **Environment Variables** (ระดับ resource) — ชุดเดิม: `DJANGO_SECRET_KEY`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_SSLMODE=disable`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CORS_ALLOWED_ORIGINS`
3. **Domains** — ตั้ง domain ให้ **service `proxy`** เป็น `https://sams.scphtrang.ac.th` (ล้าง domain เก่าที่ผูกกับ resource ที่แยกไว้ก่อนหน้านี้ เพื่อไม่ให้ชนกัน — โดเมนเดียวถูกต้องต่อ proxy เดียว)
4. Deploy

### ความจริงเรื่องโดเมนที่ต้องปรับ (สำคัญ)

- โดเมน `sams.scphtrang.ac.th` ที่(trardเก่า) **ผูกกับ Django resource รอบแรก** — หากเปลี่ยนไปใช้ compose resource:
  - เอา domain ออกจาก resource เก่า (หรือลบ resource เก่าทั้งโปรเจกต์ — ตัดสิ้นความจำ 1 นาทีโดยมี downtimew เสี้ยวน้อย)
  - จด Coolify proxy ที่ resource ใหม่ เรียบร้อยแล้วเท่านั้น
- โชคดี: DNS (Cloudflare) ไม่ต้องแก้ — ชี้เครื่อง Coolify เดียวกัน

### การหยุดระดับ HTTPS (ที่ทำงานเบื้องหลัง)

`樣proxy` chain จริง: **Cloudflare (HTTPS ปลายหน้า) → Coolify Traefik → nginx ใน compose → service ภายใน** — Django ที่ได้รับ `X-Forwarded-Proto: https` (ตั้ง `SECURE_PROXY_SSL_HEADER` กข้อความ (`settings.py` **โค้ดมีแล้ว** เมื่อ DEBUG=False — ไม่ต้องแก้) ใช้เรียก API เป็น same-origin จาก browser จึงไม่มีปัญหา CORS

### ทดสอบหลัง deploy (เปิดตาม server log)

1. `https://sams.scphtrang.ac.th/` → หน้า **front** (login SAMS) — แทนที่จะเป็น Django 404
2. `https://sams.scphtrang.ac.th/api/v1/health/` → `database: "connected"`
3. `https://sams.scphtrang.ac.th/admin/` → หน้า login Django admin ไอยขอมี branding
4. login frontend → เข้า dashboard ทุก role

### ข้อจำกัดที่ยืนยัน/ไม่ยืนยัน

- ✅ nginx config เขียนตามต้นฉบับกฎ routing จาก compose, อิมเมจ backend/frontend reuse จาก Dockerfile เดิมที่ทดสอบ build ผ่านท้องถิ่น
- ⚠️ `docker compose -f docker-compose.production.yml up` ในเครื่องยังไม่ได้รัน (Docker Desktop ปิด) — ผลจริงบน Coolify ต้องติดตามที่ log แล้วกลับมารายงาน ป. ตามที่บันทึกไว้ตามข้อ 8
### รายการปรับปรุงหลัง deploy จริง (2026-10-29)

- **ย้าย Django admin จาก `/admin/` ไป `/django-admin/`** (`backend/config/urls.py`) — เหตุผล: Next.js ใช้ prefix `/admin/*` สำหรับหน้าจัดการฝั่งบริการ (`/admin/dashboard`, `/admin/users`, …) กับ admin ของ Django ชนกันเมื่อ route ตาม prefix — ลูกเรียก `/admin/dashboard` โดนส่งเข้า Django แล้วเด้ง `/admin/login/` จนเข้าหน้าบริการไม่ได้ — ยืนยันจาก URL จริง + แก้ nginx.conf routing เป็น `(api|django-admin|static)` ให้ตรง (ทดสอบ Django test 50/50 ผ่านหลังแก้)
- ผู้ดูแลเข้า Django admin ที่ `/django-admin/` (สิทธิ์ admin user เดิมทั้งหมดเหมือนเดิม; มีพฤติกรรมเดิมทุกจุด)

