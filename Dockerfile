# ------------------------------------------------------------------
# SAMS — Django backend production image (Coolify deploy)
# Build-time steps run with DEBUG=True / SQLite so no real credentials
# are needed; the runtime container requires real environment variables:
#   DJANGO_DEBUG=False (default), DB_ENGINE=postgresql (default),
#   DJANGO_SECRET_KEY, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT,
#   DJANGO_ALLOWED_HOSTS, DJANGO_CORS_ALLOWED_ORIGINS, DB_SSLMODE
# ------------------------------------------------------------------
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# ── Build deps only (psycopg[binary] ships its own libpq) ─────────
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────
COPY backend/manage.py /app/manage.py
COPY backend/config /app/config
COPY backend/apps /app/apps
COPY backend/common /app/common
COPY backend/admin_config.py /app/admin_config.py
COPY backend/openapi-check.yaml /app/openapi-check.yaml

# ── Bake static files + manifest into the image (build-time dummies) ──
# DEBUG=False so CompressedManifestStaticFilesStorage writes staticfiles.json
# (required at runtime for {% static %}). Dummy credentials never touch a DB —
# collectstatic does not open a database connection.
RUN DJANGO_SECRET_KEY=build-dummy-not-used DJANGO_DEBUG=False \
    DB_ENGINE=postgresql DB_NAME=dummy DB_USER=dummy DB_PASSWORD=dummy DB_HOST=dummy DB_PORT=5432 \
    python manage.py collectstatic --noinput

# ── Entrypoint: migrate then serve with gunicorn ───────────────────
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 3 --timeout 60"]
