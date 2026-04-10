from django.conf import settings
from django.db import models


class Permission(models.Model):
    """权限点：resource:action"""

    codename = models.CharField(
        "编码",
        max_length=64,
        unique=True,
        help_text="如 ticket:advance，可含冒号",
    )
    name = models.CharField("名称", max_length=128)
    description = models.CharField("说明", max_length=512, blank=True)

    class Meta:
        verbose_name = "权限"
        verbose_name_plural = verbose_name
        ordering = ("codename",)

    def __str__(self):
        return self.codename


class Role(models.Model):
    name = models.CharField("名称", max_length=64, unique=True)
    slug = models.SlugField("标识", max_length=64, unique=True)
    permissions = models.ManyToManyField(
        Permission, blank=True, related_name="roles", verbose_name="权限"
    )
    description = models.CharField("说明", max_length=512, blank=True)

    class Meta:
        verbose_name = "角色"
        verbose_name_plural = verbose_name
        ordering = ("slug",)

    def __str__(self):
        return self.name


class UserRole(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="user_roles",
        verbose_name="用户",
    )
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="user_roles", verbose_name="角色"
    )

    class Meta:
        verbose_name = "用户角色"
        verbose_name_plural = verbose_name
        unique_together = ("user", "role")

    def __str__(self):
        return "%s → %s" % (self.user_id, self.role.slug)


class StagePermissionRule(models.Model):
    STAGE_CHOICES = (
        ("hcs_submit", "HCS提单"),
        ("issue_review", "问题审核"),
        ("ops_analysis", "运维人员分析"),
        ("dev_analysis", "开发人员分析"),
        ("dev_review", "开发人员闭环"),
        ("ops_closure", "运维人员闭环"),
        ("audit_close", "问题审核关闭"),
        ("closed", "问题单关闭"),
    )
    stage = models.CharField("阶段", max_length=32, choices=STAGE_CHOICES, db_index=True)
    role = models.ForeignKey(
        Role, on_delete=models.CASCADE, related_name="stage_rules", verbose_name="角色"
    )
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "阶段处理权限规则"
        verbose_name_plural = verbose_name
        unique_together = ("stage", "role")
        ordering = ("stage", "role__slug")

    def __str__(self):
        return "%s -> %s" % (self.stage, self.role.slug)
