from django.conf import settings
from django.db import models


class FieldOptionSet(models.Model):
    option_set_code = models.CharField("选项集编码", max_length=64, unique=True)
    option_set_name = models.CharField("选项集名称", max_length=128)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "field_option_set"
        verbose_name = "字段选项集"
        verbose_name_plural = verbose_name


class FieldDefinition(models.Model):
    class FieldType(models.TextChoices):
        TEXT = "text", "文本"
        DATE = "date", "日期"
        RICH_TEXT = "rich_text", "富文本"
        SELECT = "select", "下拉"
        DOER_TAG = "doer_tag", "Doer标注"

    field_code = models.CharField("字段编码", max_length=128, unique=True)
    field_name = models.CharField("字段名称", max_length=128)
    field_type = models.CharField(
        "字段类型", max_length=32, choices=FieldType.choices, default=FieldType.TEXT
    )
    option_set = models.ForeignKey(
        FieldOptionSet,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="field_definitions",
    )
    validation_json = models.JSONField("校验规则", null=True, blank=True)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "field_definition"
        verbose_name = "字段定义"
        verbose_name_plural = verbose_name


class FieldOptionItem(models.Model):
    option_set = models.ForeignKey(
        FieldOptionSet, on_delete=models.CASCADE, related_name="items"
    )
    option_value = models.CharField("值", max_length=256)
    option_label = models.CharField("显示名", max_length=256)
    order_no = models.PositiveIntegerField("排序", default=0)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "field_option_item"
        ordering = ["option_set_id", "order_no"]
        verbose_name = "选项项"
        verbose_name_plural = verbose_name


class FormSchema(models.Model):
    class SchemaStatus(models.TextChoices):
        DRAFT = "draft", "草稿"
        PUBLISHED = "published", "已发布"
        OFFLINE = "offline", "已下线"

    schema_code = models.CharField("表单编码", max_length=64, db_index=True)
    schema_name = models.CharField("表单名称", max_length=128)
    version_no = models.PositiveIntegerField("版本号", default=1)
    status = models.CharField(
        "状态",
        max_length=16,
        choices=SchemaStatus.choices,
        default=SchemaStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField("发布时间", null=True, blank=True)

    class Meta:
        db_table = "form_schema"
        unique_together = [("schema_code", "version_no")]
        verbose_name = "表单版本"
        verbose_name_plural = verbose_name


class StageFieldBinding(models.Model):
    schema = models.ForeignKey(
        FormSchema, on_delete=models.CASCADE, related_name="stage_field_bindings"
    )
    stage_code = models.CharField("阶段编码", max_length=64, db_index=True)
    field = models.ForeignKey(
        FieldDefinition, on_delete=models.CASCADE, related_name="stage_bindings"
    )
    is_visible = models.BooleanField("是否显示", default=True)
    is_required = models.BooleanField("是否必填", default=False)
    is_readonly = models.BooleanField("是否只读", default=False)
    display_order = models.PositiveIntegerField("显示顺序", default=0)

    class Meta:
        db_table = "stage_field_binding"
        unique_together = [("schema", "stage_code", "field")]
        verbose_name = "阶段字段绑定"
        verbose_name_plural = verbose_name


class FieldRule(models.Model):
    schema = models.ForeignKey(
        FormSchema, on_delete=models.CASCADE, related_name="field_rules"
    )
    stage_code = models.CharField("阶段编码", max_length=64, db_index=True)
    rule_name = models.CharField("规则名", max_length=128)
    condition_expr = models.TextField("条件表达式", blank=True)
    action_expr = models.TextField("动作表达式", blank=True)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "field_rule"
        verbose_name = "字段联动规则"
        verbose_name_plural = verbose_name


class TicketFieldValue(models.Model):
    ticket = models.ForeignKey(
        "ticket.Ticket", on_delete=models.CASCADE, related_name="field_values"
    )
    stage_code = models.CharField("阶段编码", max_length=64, db_index=True)
    field_code = models.CharField("字段编码", max_length=128, db_index=True)
    field_value_text = models.TextField("文本值", blank=True)
    field_value_json = models.JSONField("结构化值", null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_field_value_updates",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket_field_value"
        verbose_name = "工单字段值"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["ticket", "stage_code"]),
            models.Index(fields=["ticket", "stage_code", "field_code"]),
        ]
