"""生产环境：强制关键环境变量、HTTPS 代理、静态资源 WhiteNoise。"""
import os

from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = os.environ.get("DJANGO_DEBUG", "0").strip() == "1"

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if h.strip()
]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured(
        "生产环境必须设置 DJANGO_ALLOWED_HOSTS（逗号分隔，例如 example.com,www.example.com）"
    )

if not SECRET_KEY:
    raise ImproperlyConfigured("生产环境必须设置 DJANGO_SECRET_KEY")

if os.environ.get("DJANGO_SECRET_KEY_STRENGTH_CHECK", "1") == "1":
    if SECRET_KEY.startswith("django-insecure") or len(SECRET_KEY) < 40:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY 过弱：请使用高强度的随机密钥（建议 length>=40，且勿使用 django-insecure 前缀）"
        )

# WhiteNoise：置于 SecurityMiddleware 之后
_security_idx = MIDDLEWARE.index("django.middleware.security.SecurityMiddleware")
MIDDLEWARE.insert(_security_idx + 1, "whitenoise.middleware.WhiteNoiseMiddleware")

STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = True

if os.environ.get("DJANGO_BEHIND_HTTPS_PROXY", "0").strip() == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = (
        os.environ.get("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "1") == "1"
    )
    SECURE_HSTS_PRELOAD = os.environ.get("DJANGO_SECURE_HSTS_PRELOAD", "0") == "1"
else:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in _csrf.split(",") if o.strip()
]
