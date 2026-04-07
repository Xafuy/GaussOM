"""
根据 DJANGO_ENV 选择配置：development（默认）或 production。
"""
import os

_env = os.environ.get("DJANGO_ENV", "development").lower()
if _env == "production":
    from .production import *  # noqa: F403, E402, F401
else:
    from .development import *  # noqa: F403, E402, F401
