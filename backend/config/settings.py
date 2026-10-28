"""
SAMS — Student Attendance Management System
Django settings (config.settings)

Environment validation is enforced at startup per SAMS spec §15:
- No hardcoded credentials
- SQLite is forbidden in production (DEBUG=False)
- QR TTL / grace values are validated for sanity
"""

from pathlib import Path
import logging
import os
import secrets

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# .env loader (zero-dependency)
# ---------------------------------------------------------------------------
def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_env_file(BASE_DIR / ".env")


def env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and (value is None or value == ""):
        raise RuntimeError(
            f"Missing required environment variable: {name}. "
            "See backend/.env.example"
        )
    return value


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in (
        "1", "true", "yes", "on",
    )


def env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        raise RuntimeError(f"Environment variable {name} must be an integer")


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
PROJECT_NAME = "SAMS"
PROJECT_VERSION = "1.0.0"

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    # Dev-only ephemeral fallback. Production (DEBUG=False) must provide a real
    # secret — enforced further below. Never committed to source control.
    default=secrets.token_urlsafe(64),
)
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = [
    h.strip()
    for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

# In production, DJANGO_SECRET_KEY must come from the environment (not the
# ephemeral fallback) and DEBUG must not be True on public deployments.
if not DEBUG and os.environ.get("DJANGO_SECRET_KEY", "") == "":
    raise RuntimeError(
        "DJANGO_SECRET_KEY is required in production (DJANGO_DEBUG=False)."
    )

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # SAMS
    "apps.accounts",
    "apps.academics",
    "apps.courses",
    "apps.schedules",
    "apps.attendance",
    "apps.reports",
    "apps.audit",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database — Supabase PostgreSQL (production). SQLite only as a local dev
# fallback and ONLY when DEBUG=True (spec §12: no SQLite in production).
# ---------------------------------------------------------------------------
DB_ENGINE = env("DB_ENGINE", "postgresql")
if DB_ENGINE == "postgresql":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env("DB_NAME", required=True),
            "USER": env("DB_USER", required=True),
            "PASSWORD": env("DB_PASSWORD", required=True),
            "HOST": env("DB_HOST", required=True),
            "PORT": env("DB_PORT", "5432"),
            "OPTIONS": {
                "sslmode": env("DB_SSLMODE", "require"),
            },
            # Supabase compatibility: keep connections sane behind pgbouncer.
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 0),
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif DB_ENGINE == "sqlite":
    if not DEBUG:
        raise RuntimeError(
            "SQLite is not allowed as a production database (SAMS spec §12). "
            "Set DB_ENGINE=postgresql with real credentials."
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    raise RuntimeError(f"Unsupported DB_ENGINE: {DB_ENGINE}")


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
]

AUTH_USER_MODEL = "accounts.User"


# ---------------------------------------------------------------------------
# Internationalisation — Thai language, Asia/Bangkok timezone
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "th"
TIME_ZONE = env("TIME_ZONE", "Asia/Bangkok")
USE_I18N = True
USE_TZ = True


# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "600/hour",
        # Scoped buckets
        "login": "10/min",
        "checkin": "20/min",
        "csv_import": "5/hour",
    },
    "EXCEPTION_HANDLER": "common.exceptions.sams_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("common.renderers.SamsJSONRenderer",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SAMS API — Student Attendance Management System",
    "DESCRIPTION": "REST API ของระบบบริหารจัดการการเข้าเรียนผ่าน QR Code (SAMS)",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
}

# SimpleJWT — short-lived access tokens, rotating refresh tokens with
# blacklist-based revocation (prevents reuse of rotated tokens).
ACCESS_TOKEN_LIFETIME_MINUTES = env_int("ACCESS_TOKEN_LIFETIME_MINUTES", 10)
REFRESH_TOKEN_LIFETIME_DAYS = env_int("REFRESH_TOKEN_LIFETIME_DAYS", 7)
if not (1 <= ACCESS_TOKEN_LIFETIME_MINUTES <= 240):
    raise RuntimeError("ACCESS_TOKEN_LIFETIME_MINUTES must be between 1 and 240")
if not (1 <= REFRESH_TOKEN_LIFETIME_DAYS <= 30):
    raise RuntimeError("REFRESH_TOKEN_LIFETIME_DAYS must be between 1 and 30")

import datetime

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": datetime.timedelta(minutes=ACCESS_TOKEN_LIFETIME_MINUTES),
    "REFRESH_TOKEN_LIFETIME": datetime.timedelta(days=REFRESH_TOKEN_LIFETIME_DAYS),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


# QR token policy (validated)
QR_TOKEN_TTL_SECONDS = env_int("ATTENDANCE_QR_TTL_SECONDS", 30)
QR_TOKEN_GRACE_SECONDS = env_int("ATTENDANCE_QR_TOKEN_DISPLAY_GRACE_SECONDS", 10)
CHECKIN_GRACE_SECONDS = env_int("ATTENDANCE_CHECKIN_GRACE_SECONDS", 0)
DEFAULT_LATE_THRESHOLD_MINUTES = env_int("ATTENDANCE_LATE_THRESHOLD_MINUTES", 15)
if not (5 <= QR_TOKEN_TTL_SECONDS <= 3600):
    raise RuntimeError("ATTENDANCE_QR_TTL_SECONDS must be between 5 and 3600")
if not (0 <= CHECKIN_GRACE_SECONDS <= 3600):
    raise RuntimeError("ATTENDANCE_CHECKIN_GRACE_SECONDS must be between 0 and 3600")
if not (0 <= DEFAULT_LATE_THRESHOLD_MINUTES <= 240):
    raise RuntimeError("ATTENDANCE_LATE_THRESHOLD_MINUTES must be between 0 and 240")


# ---------------------------------------------------------------------------
# CORS / Cookies — Next.js on an allowed origin talks to this API with
# credentials so the HttpOnly refresh-token cookie works.
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in env("DJANGO_CORS_ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = CORS_ALLOWED_ORIGINS

REFRESH_COOKIE_NAME = "sams_refresh"
REFRESH_COOKIE_MAX_AGE = REFRESH_TOKEN_LIFETIME_DAYS * 24 * 3600


# ---------------------------------------------------------------------------
# Security settings (production hardening)
# ---------------------------------------------------------------------------
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", 2 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True


# ---------------------------------------------------------------------------
# Static / i18n
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ---------------------------------------------------------------------------
# Logging — never log tokens or passwords at full value (spec §16)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {"()": "django.utils.log.RequireDebugFalse"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "file": {
            "class": "logging.FileHandler",
            "filename": BASE_DIR / "logs" / "sams.log",
            "formatter": "verbose",
            "filters": ["require_debug_false"],
        },
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO"},
        "sams": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}
os.makedirs(BASE_DIR / "logs", exist_ok=True)
