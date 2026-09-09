"""Local defaults are isolated. Production requires explicit secrets and PostgreSQL."""

import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set SECRET_KEY before running in production.")
    SECRET_KEY = "development-only-firstglanceknox-not-for-production-2026"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],testserver").split(",")
SITE_URL = os.getenv("SITE_URL", "http://127.0.0.1:8765").rstrip("/")
CSRF_TRUSTED_ORIGINS = [v for v in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if v]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "accounts",
    "operations",
    "marketing",
    "portal",
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
    "config.middleware.RequestSafetyMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "config.context_processors.business",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///" + (BASE_DIR / "db.sqlite3").as_posix())
DATABASES = {"default": dj_database_url.parse(DATABASE_URL, conn_max_age=60)}
if not DEBUG and DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":
    raise ImproperlyConfigured("Production requires a PostgreSQL DATABASE_URL.")
AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
PRIVATE_MEDIA_ROOT = BASE_DIR / "private_media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
if os.getenv("AWS_STORAGE_BUCKET_NAME"):
    STORAGES["default"] = {"BACKEND": "storages.backends.s3.S3Storage"}
    AWS_STORAGE_BUCKET_NAME = os.environ["AWS_STORAGE_BUCKET_NAME"]
    AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL")
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = True
    AWS_S3_FILE_OVERWRITE = False
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.filebased.EmailBackend")
EMAIL_FILE_PATH = BASE_DIR / ".local" / "emails"
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "FirstGlanceKnox <noreply@example.invalid>")
BUSINESS_NAME = "FirstGlanceKnox"
BUSINESS_PHONE = os.getenv("BUSINESS_PHONE", "")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "")
PAYMENT_INSTRUCTIONS = os.getenv(
    "PAYMENT_INSTRUCTIONS",
    "Contact FirstGlanceKnox to arrange payment. Please include your invoice number with your payment.",
)
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "/crew/"
LOGOUT_REDIRECT_URL = "/"
PORTAL_TOKEN_MAX_AGE = int(os.getenv("PORTAL_TOKEN_MAX_AGE", "604800"))
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 43200
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
# Set only behind a trusted proxy that strips client-supplied forwarding headers.
if os.getenv("TRUST_PROXY_HTTPS") == "true":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
REDIS_URL = os.getenv("REDIS_URL", "")
CACHES = (
    {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
    if REDIS_URL
    else {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
)
if not DEBUG and not REDIS_URL:
    raise ImproperlyConfigured("Production requires REDIS_URL for shared rate limiting and jobs.")
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL or "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = None
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_IGNORE_RESULT = True
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TIMEZONE = TIME_ZONE
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "")
PUSH_ENABLED = os.getenv("PUSH_ENABLED", "false").lower() == "true"
EMAIL_TASKS_ENABLED = os.getenv("EMAIL_TASKS_ENABLED", "false").lower() == "true"
NOTIFICATIONS_FANOUT_ENABLED = PUSH_ENABLED
CELERY_BEAT_SCHEDULE = {"operations-maintenance": {"task": "operations.tasks.maintenance", "schedule": 300.0}}
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
