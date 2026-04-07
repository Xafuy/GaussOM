from django.conf import settings
from django.db import models


class ConfigNamespace(models.Model):
    namespace_code = models.CharField("命名空间编码", max_length=64, unique=True)
    namespace_name = models.CharField("命名空间名称", max_length=128)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "config_namespace"
        verbose_name = "配置命名空间"
        verbose_name_plural = verbose_name


class ConfigItem(models.Model):
    class ValueType(models.TextChoices):
        STRING = "string", "字符串"
        NUMBER = "number", "数字"
        BOOL = "bool", "布尔"
        JSON = "json", "JSON"

    namespace = models.ForeignKey(
        ConfigNamespace, on_delete=models.CASCADE, related_name="items"
    )
    item_key = models.CharField("配置键", max_length=128)
    item_name = models.CharField("配置名称", max_length=128)
    value_type = models.CharField(
        "值类型", max_length=16, choices=ValueType.choices, default=ValueType.STRING
    )
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "config_item"
        unique_together = [("namespace", "item_key")]
        verbose_name = "配置项"
        verbose_name_plural = verbose_name


class ConfigVersion(models.Model):
    class VersionStatus(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        OFFLINE = "offline", "已下线"

    namespace = models.ForeignKey(
        ConfigNamespace, on_delete=models.CASCADE, related_name="versions"
    )
    version_no = models.PositiveIntegerField("版本号", default=1)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
        db_index=True,
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="config_versions_published",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "config_version"
        verbose_name = "配置版本"
        verbose_name_plural = verbose_name


class ConfigValue(models.Model):
    version = models.ForeignKey(
        ConfigVersion, on_delete=models.CASCADE, related_name="values"
    )
    config_item = models.ForeignKey(
        ConfigItem, on_delete=models.CASCADE, related_name="values"
    )
    config_value_json = models.JSONField("配置值", null=True, blank=True)

    class Meta:
        db_table = "config_value"
        unique_together = [("version", "config_item")]
        verbose_name = "配置值"
        verbose_name_plural = verbose_name


class ConfigPublishRecord(models.Model):
    namespace = models.ForeignKey(
        ConfigNamespace, on_delete=models.CASCADE, related_name="publish_records"
    )
    from_version = models.ForeignKey(
        ConfigVersion,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publish_records_from",
    )
    to_version = models.ForeignKey(
        ConfigVersion,
        on_delete=models.CASCADE,
        related_name="publish_records_to",
    )
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="config_publish_records",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "config_publish_record"
        verbose_name = "配置发布记录"
        verbose_name_plural = verbose_name


class ConfigAuditLog(models.Model):
    namespace = models.ForeignKey(
        ConfigNamespace, on_delete=models.CASCADE, related_name="audit_logs"
    )
    item_key = models.CharField("配置键", max_length=128, db_index=True)
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="config_audit_logs",
    )
    before_json = models.JSONField("变更前", null=True, blank=True)
    after_json = models.JSONField("变更后", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "config_audit_log"
        verbose_name = "配置审计日志"
        verbose_name_plural = verbose_name
