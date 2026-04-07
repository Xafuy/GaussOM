from django.conf import settings
from django.db import models


class Ticket(models.Model):
    class SourceType(models.TextChoices):
        HCS = "HCS", "HCS"
        BU = "BU", "BU"
        TEMP = "temp", "临时提单"
        SELF = "self", "运维自提单"

    class IssueType(models.TextChoices):
        KERNEL = "kernel", "内核"
        CONTROL = "control", "管控"
        OTHER = "other", "其他"

    class TicketStatus(models.TextChoices):
        PROCESSING = "processing", "处理中"
        CLOSED = "closed", "已关闭"
        CANCELLED = "cancelled", "已取消"

    ticket_no = models.CharField("工单号", max_length=64, unique=True, db_index=True)
    source_type = models.CharField(
        "来源类型", max_length=16, choices=SourceType.choices, db_index=True
    )
    current_stage_code = models.CharField("当前阶段", max_length=64, db_index=True)
    current_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="current_tickets",
    )
    creator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )
    creator_group = models.ForeignKey(
        "system.SysOrgGroup",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_tickets",
    )
    is_quality_issue = models.BooleanField("是否质量问题", null=True, blank=True)
    is_consult_issue = models.BooleanField("是否咨询问题", null=True, blank=True)
    issue_type = models.CharField(
        "问题类型",
        max_length=16,
        choices=IssueType.choices,
        blank=True,
        db_index=True,
    )
    priority = models.CharField("优先级", max_length=16, blank=True, db_index=True)
    status = models.CharField(
        "工单状态",
        max_length=16,
        choices=TicketStatus.choices,
        default=TicketStatus.PROCESSING,
        db_index=True,
    )
    opened_at = models.DateTimeField("开单时间", auto_now_add=True)
    closed_at = models.DateTimeField("关单时间", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ticket"
        verbose_name = "工单"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["current_stage_code", "current_assignee", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return self.ticket_no


class TicketStageDef(models.Model):
    stage_code = models.CharField("阶段编码", max_length=64, unique=True)
    stage_name = models.CharField("阶段名称", max_length=128)
    stage_order = models.PositiveSmallIntegerField("排序", default=0)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "ticket_stage_def"
        ordering = ["stage_order"]
        verbose_name = "阶段定义"
        verbose_name_plural = verbose_name


class TicketTransition(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="transitions"
    )
    from_stage_code = models.CharField("来源阶段", max_length=64, blank=True)
    to_stage_code = models.CharField("目标阶段", max_length=64, db_index=True)
    action_code = models.CharField("动作", max_length=32, db_index=True)
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_transitions_operated",
    )
    from_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_transitions_from_assignee",
    )
    to_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ticket_transitions_to_assignee",
    )
    comment = models.TextField("备注", blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ticket_transition"
        verbose_name = "流转记录"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
            models.Index(fields=["to_stage_code", "created_at"]),
        ]


class TicketAssigneeHistory(models.Model):
    class AssignType(models.TextChoices):
        AUTO = "auto", "自动分单"
        MANUAL = "manual", "手工"
        SPECIAL = "special", "专项"
        CONTROL = "control", "管控"
        DESIGNATED = "designated", "指定人员"

    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="assignee_histories"
    )
    stage_code = models.CharField("阶段", max_length=64, db_index=True)
    assignee_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ticket_assignee_histories",
    )
    assign_type = models.CharField(
        "分配类型", max_length=16, choices=AssignType.choices, default=AssignType.AUTO
    )
    assigned_at = models.DateTimeField("分配时间", auto_now_add=True)

    class Meta:
        db_table = "ticket_assignee_history"
        verbose_name = "处理人历史"
        verbose_name_plural = verbose_name


class TicketOperationLog(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="operation_logs"
    )
    operation_type = models.CharField("操作类型", max_length=64, db_index=True)
    operator_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ticket_operation_logs",
    )
    before_json = models.JSONField("变更前", null=True, blank=True)
    after_json = models.JSONField("变更后", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_operation_log"
        verbose_name = "工单审计日志"
        verbose_name_plural = verbose_name
