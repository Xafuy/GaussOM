from django.conf import settings
from django.db import models


class DispatchPolicy(models.Model):
    policy_code = models.CharField("策略编码", max_length=64, unique=True)
    policy_name = models.CharField("策略名称", max_length=128)
    status = models.CharField(max_length=16, default="active", db_index=True)
    effective_from = models.DateTimeField("生效开始", null=True, blank=True)
    effective_to = models.DateTimeField("生效结束", null=True, blank=True)
    version_no = models.PositiveIntegerField("版本号", default=1)

    class Meta:
        db_table = "dispatch_policy"
        verbose_name = "分单策略"
        verbose_name_plural = verbose_name


class DispatchRule(models.Model):
    policy = models.ForeignKey(
        DispatchPolicy, on_delete=models.CASCADE, related_name="rules"
    )
    rule_code = models.CharField("规则编码", max_length=64)
    priority_no = models.PositiveIntegerField("优先级(越小越先)", default=0)
    condition_expr = models.JSONField("条件表达式", null=True, blank=True)
    action_type = models.CharField("动作类型", max_length=64, db_index=True)
    action_param_json = models.JSONField("动作参数", null=True, blank=True)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "dispatch_rule"
        verbose_name = "分单规则"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["policy", "priority_no", "status"]),
        ]


class DispatchCursor(models.Model):
    class BizScene(models.TextChoices):
        DAY = "day", "白班大循环"
        KERNEL = "kernel", "内核"
        CONTROL = "control", "管控"
        SPECIAL = "special", "专项"

    schedule = models.ForeignKey(
        "duty.DutySchedule",
        on_delete=models.CASCADE,
        related_name="dispatch_cursors",
    )
    biz_scene = models.CharField(
        "业务场景", max_length=32, choices=BizScene.choices, db_index=True
    )
    current_member = models.ForeignKey(
        "duty.DutyScheduleMember",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dispatch_cursors",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "dispatch_cursor"
        unique_together = [("schedule", "biz_scene")]
        verbose_name = "轮询游标"
        verbose_name_plural = verbose_name


class DispatchDecisionLog(models.Model):
    ticket = models.ForeignKey(
        "ticket.Ticket", on_delete=models.CASCADE, related_name="dispatch_decisions"
    )
    policy = models.ForeignKey(
        DispatchPolicy,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
    )
    hit_rule = models.ForeignKey(
        DispatchRule,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decision_logs",
    )
    decision_path_json = models.JSONField("决策路径", null=True, blank=True)
    final_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="dispatch_decision_as_final",
    )
    fallback_reason = models.CharField("兜底原因", max_length=256, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "dispatch_decision_log"
        verbose_name = "分单决策日志"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["ticket", "created_at"]),
        ]


class DispatchCompensationRecord(models.Model):
    class TransferType(models.TextChoices):
        CONTROL = "control", "管控"
        SPECIAL = "special", "专项"
        DESIGNATED = "designated", "指定"

    class CompensationType(models.TextChoices):
        EXTRA_TICKET = "extra_ticket", "转单人补单"
        UPDATE_RECEIVE_TIME = "update_receive_time", "更新接单时间"
        SKIP_NEXT = "skip_next", "跳过下次接单"

    ticket = models.ForeignKey(
        "ticket.Ticket", on_delete=models.CASCADE, related_name="dispatch_compensations"
    )
    transfer_type = models.CharField(
        "转单类型", max_length=16, choices=TransferType.choices
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dispatch_comp_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dispatch_comp_to",
    )
    compensation_type = models.CharField(
        "补偿类型", max_length=32, choices=CompensationType.choices
    )
    status = models.CharField(max_length=16, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "dispatch_compensation_record"
        verbose_name = "转单补偿记录"
        verbose_name_plural = verbose_name
