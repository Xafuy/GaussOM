"""
共享配置：应用、中间件、数据库、日志等。
敏感项通过环境变量注入（见 .env.example / design/生产化收口清单.md）。
"""
import logging
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip()

LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "Asia/Shanghai"
USE_I18N = True
USE_TZ = True

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.system",
    "apps.duty",
    "apps.ticket",
    "apps.dispatch",
    "apps.form",
    "apps.config_center",
    "apps.analytics",
]

AUTH_USER_MODEL = "system.SysUser"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gaussdbom.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "gaussdbom.wsgi.application"

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


def _build_databases():
    engine = os.environ.get("DJANGO_DB_ENGINE", "sqlite3").lower().strip()
    if engine in ("postgresql", "postgres", "pgsql"):
        name = os.environ.get("DJANGO_DB_NAME", "").strip()
        if not name:
            raise ImproperlyConfigured(
                "生产使用 PostgreSQL 时需设置 DJANGO_DB_NAME（及连接参数）。"
            )
        return {
            "default": {
                "ENGINE": "django.db.backends.postgresql",
                "NAME": name,
                "USER": os.environ.get("DJANGO_DB_USER", ""),
                "PASSWORD": os.environ.get("DJANGO_DB_PASSWORD", ""),
                "HOST": os.environ.get("DJANGO_DB_HOST", "localhost"),
                "PORT": os.environ.get("DJANGO_DB_PORT", "5432"),
                "CONN_MAX_AGE": int(os.environ.get("DJANGO_DB_CONN_MAX_AGE", "60")),
            }
        }
    path = os.environ.get("DJANGO_SQLITE_PATH", "")
    name = Path(path).expanduser() if path else BASE_DIR / "db.sqlite3"
    return {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(name),
        }
    }


DATABASES = _build_databases()


STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

_log_level = os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()
_root_level = _log_level if _log_level in logging._nameToLevel else "INFO"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": _root_level,
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": _root_level,
            "propagate": False,
        },
    },
}
