"""本地开发：默认宽松；仍可通过环境变量覆盖 Allowed Hosts 等。"""
import os

from .base import *

DEBUG = True

_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
if _hosts:
    ALLOWED_HOSTS = [h.strip() for h in _hosts.split(",") if h.strip()]
else:
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]

if not SECRET_KEY:
    SECRET_KEY = "django-insecure-dev-only-not-for-production"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
