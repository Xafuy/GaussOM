import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

_IMG_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


@register.filter
def render_rich_text(value):
    """
    将文本中的 Markdown 图片语法渲染为预览图，并保留换行。
    仅支持 ![alt](url) 这一最小语法，避免引入重型 Markdown 依赖。
    """
    text = "" if value is None else str(value)
    safe_text = escape(text)

    def repl(match):
        alt = escape(match.group(1) or "图片")
        src = escape(match.group(2) or "")
        return (
            '<img src="%s" alt="%s" '
            'style="max-width:100%%;height:auto;border:1px solid rgba(0,0,0,.08);'
            'border-radius:8px;margin:6px 0;display:block;" />'
        ) % (src, alt)

    rendered = _IMG_MD_RE.sub(repl, safe_text)
    rendered = rendered.replace("\n", "<br>")
    return mark_safe(rendered)

