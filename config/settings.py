"""Settings for the Guidance Office Management System.

Every environment-specific value comes from environment variables, so the same code
runs locally (SQLite or Postgres) and on Vercel + Supabase. See .env.example.
"""

from __future__ import annotations

import base64
import hashlib
import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as message_constants
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


TESTING = len(sys.argv) > 1 and sys.argv[1] == "test"
ON_VERCEL = bool(os.environ.get("VERCEL"))
VERCEL_ENV = env("VERCEL_ENV")  # production, preview or development

DEBUG = env_bool("DJANGO_DEBUG", default=False)

SECRET_KEY = env("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    if DEBUG or TESTING:
        SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"
    else:
        raise ImproperlyConfigured("Set the DJANGO_SECRET_KEY environment variable.")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
if TESTING:
    ALLOWED_HOSTS.append("testserver")
if ON_VERCEL:
    for _var in ("VERCEL_URL", "VERCEL_BRANCH_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        _host = env(_var)
        if _host and _host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(_host)

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]", "testserver"}
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS") + [
    f"https://{host}"
    for host in ALLOWED_HOSTS
    if host not in _LOCAL_HOSTS and not host.startswith(".") and host != "*"
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "axes",
    "apps.core",
    "apps.accounts",
    "apps.audit",
    "apps.students",
    "apps.scheduling",
    "apps.discipline",
    "apps.counseling",
    "apps.interventions",
    "apps.protection",
    "apps.reports",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "apps.core.request_context.RequestContextMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    # django-axes must be last.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.app_context",
            ],
            "builtins": [
                "django.templatetags.static",
                "django.contrib.humanize.templatetags.humanize",
                "apps.core.templatetags.ui",
            ],
        },
    },
]

# --- Database -----------------------------------------------------------------------------
DATABASE_URL = env("DATABASE_URL")
if DATABASE_URL:
    _db = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=env_int("DB_CONN_MAX_AGE", 0),
        conn_health_checks=True,
        ssl_require=env_bool("DB_SSL_REQUIRE", True),
    )
    # Supabase's shared pooler in transaction mode (port 6543) can't hold cursors
    # across transactions, so Django must not use server-side cursors there.
    if str(_db.get("PORT")) == "6543" or env_bool("DB_TRANSACTION_POOLER"):
        _db["DISABLE_SERVER_SIDE_CURSORS"] = True
    DATABASES = {"default": _db}
elif ON_VERCEL:
    raise ImproperlyConfigured(
        "DATABASE_URL must be set on Vercel (Supabase transaction pooler URL, port 6543)."
    )
else:
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }
# One request = one transaction, so a record, its audit entry and its follow-ups
# are saved together or not at all.
DATABASES["default"]["ATOMIC_REQUESTS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentication ---------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "core:dashboard"
LOGOUT_REDIRECT_URL = "accounts:login"

# Sliding idle timeout: the session expires after N minutes without a request.
SESSION_COOKIE_AGE = env_int("SESSION_IDLE_TIMEOUT_MINUTES", 30) * 60
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

# Lock an account+IP pair for 30 minutes after 5 failed sign-ins.
AXES_ENABLED = env_bool("AXES_ENABLED", not TESTING)
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/locked_out.html"
AXES_CLIENT_IP_CALLABLE = "apps.core.net.get_client_ip"
# Header holding the real client IP when behind a trusted proxy (Vercel sets X-Real-IP).
CLIENT_IP_HEADER = env("CLIENT_IP_HEADER", "HTTP_X_REAL_IP" if ON_VERCEL else "")

# --- Internationalisation -----------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Manila"
USE_I18N = True
USE_TZ = True

# --- Static files and uploads -------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"  # never served directly: downloads go through a permission check
MEDIA_ROOT = BASE_DIR / "media"

STORAGE_S3_BUCKET = env("STORAGE_S3_BUCKET")
if STORAGE_S3_BUCKET:
    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": STORAGE_S3_BUCKET,
            "endpoint_url": env("STORAGE_S3_ENDPOINT_URL"),
            "region_name": env("STORAGE_S3_REGION"),
            "access_key": env("STORAGE_S3_ACCESS_KEY_ID"),
            "secret_key": env("STORAGE_S3_SECRET_ACCESS_KEY"),
            "addressing_style": "path",
            "signature_version": "s3v4",
            "default_acl": None,
            "file_overwrite": False,
            "querystring_auth": True,
            "querystring_expire": 60,
        },
    }
else:
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
# Vercel's filesystem is read-only, so attachments need object storage there.
ATTACHMENTS_ENABLED = bool(STORAGE_S3_BUCKET) or not ON_VERCEL
# Vercel Functions accept request bodies up to 4.5 MB, so keep uploads under that.
MAX_UPLOAD_SIZE_MB = env_int("MAX_UPLOAD_SIZE_MB", 4)
ALLOWED_UPLOAD_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"]

# --- Email --------------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env_int("EMAIL_PORT", 587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
    EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "guidance-office@localhost")

# --- Security headers ---------------------------------------------------------------------
if ON_VERCEL or env_bool("DJANGO_BEHIND_PROXY"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    # Vercel already redirects HTTP to HTTPS at the edge; the test client speaks plain HTTP.
    SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", not ON_VERCEL and not TESTING)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("DJANGO_HSTS_SECONDS", 60 * 60 * 24 * 365)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("DJANGO_HSTS_INCLUDE_SUBDOMAINS", False)
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "object-src": [CSP.NONE],
}
SILENCED_SYSTEM_CHECKS = ["security.W008"] if ON_VERCEL else []

# --- Field encryption ---------------------------------------------------------------------
FIELD_ENCRYPTION_KEYS = env_list("FIELD_ENCRYPTION_KEYS")
if not FIELD_ENCRYPTION_KEYS:
    if DEBUG or TESTING:
        # Development only: derive a stable key from SECRET_KEY.
        FIELD_ENCRYPTION_KEYS = [
            base64.urlsafe_b64encode(hashlib.sha256(SECRET_KEY.encode()).digest()).decode()
        ]
    else:
        raise ImproperlyConfigured(
            "Set FIELD_ENCRYPTION_KEYS. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )

# --- Application settings -----------------------------------------------------------------
SITE_NAME = env("SITE_NAME", "Guidance Office Management System")
CRON_SECRET = env("CRON_SECRET")
REMINDER_LOOKAHEAD_DAYS = env_int("REMINDER_LOOKAHEAD_DAYS", 2)

# DO 006, s. 2026 timelines for learner rights and protection (LRP) cases.
# The risk-assessment target is a school-set target: the order gives no deadline for it.
LRP_RISK_ASSESSMENT_TARGET_HOURS = env_int("LRP_RISK_ASSESSMENT_TARGET_HOURS", 24)
LRP_INTAKE_DEADLINE_HOURS = 48  # Incident Report and Intake Sheet to the disciplining authority
LRP_FACT_FINDING_DAYS = 10  # findings to the School Head (calendar days)
LRP_FORWARD_DAYS = 30  # results to the SDS and RD, counted from receipt of the report
# DO 006, s. 2026 due process for penalised cases (calendar days).
DUE_PROCESS_ANSWER_DAYS = 10
APPEAL_DAYS = 15  # to the SDS or RD
BULLYING_APPEAL_DAYS = 10  # to the Office of the Undersecretary for Legal and Legislative Affairs

MESSAGE_TAGS = {message_constants.ERROR: "danger"}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}
