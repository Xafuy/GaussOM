from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """扩展用户：业务身份、W3 预留"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="用户",
    )
    identities = models.CharField(
        "业务身份",
        max_length=64,
        blank=True,
        help_text="逗号分隔：管控control、bu、ops、dev、guest",
    )
    w3_subject = models.CharField(
        "W3 外部标识",
        max_length=256,
        blank=True,
        db_index=True,
        help_text="接入 W3 后填写；预留",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "用户资料"
        verbose_name_plural = verbose_name

    def identity_list(self):
        if not self.identities.strip():
            return []
        return [s.strip() for s in self.identities.split(",") if s.strip()]
