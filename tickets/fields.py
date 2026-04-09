import json

from django.db import models


class JSONTextField(models.TextField):
    """
    以 TEXT 存储 JSON，行为上接近 JSONField，但不依赖 SQLite 的 JSON1 扩展。
    适用于 Windows 自带解释器捆绑的旧版 SQLite。
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("default", dict)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return {}
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}

    def to_python(self, value):
        if isinstance(value, (dict, list)):
            return value
        if value in (None, ""):
            return {}
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return {}

    def get_prep_value(self, value):
        if value is None:
            return None
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)
