from django.conf import settings
from django.db import models

from .fields import JSONTextField


class TicketStage(models.TextChoices):
    """与需求文档一致的七个阶段（含 HCS 提单作为首阶段）"""

    HCS_SUBMIT = "hcs_submit", "HCS提单"
    ISSUE_REVIEW = "issue_review", "问题审核"
    OPS_ANALYSIS = "ops_analysis", "运维人员分析"
    DEV_ANALYSIS = "dev_analysis", "开发人员分析"
    DEV_REVIEW = "dev_review", "开发人员审核"
    OPS_CLOSURE = "ops_closure", "运维人员闭环"
    AUDIT_CLOSE = "audit_close", "问题审核关闭"


class Ticket(models.Model):
    """运维单主表；动态字段逐步收敛到字段引擎，当前用 JSON 承载草稿值"""

    number = models.PositiveIntegerField("单号", unique=True, default=0, editable=False)
    stage = models.CharField(
        "阶段",
        max_length=32,
        choices=TicketStage.choices,
        default=TicketStage.HCS_SUBMIT,
        db_index=True,
    )
    title = models.CharField("标题", max_length=512)
    description = models.TextField("描述", blank=True)
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reported_tickets",
        verbose_name="提单人",
    )
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
        verbose_name="当前处理人",
    )
    is_self_service = models.BooleanField("运维自提单", default=False)
    extra_data = JSONTextField("阶段字段(JSON)", default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "运维单"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)

    def __str__(self):
        disp = self.number if self.number else self.pk
        return "#%s %s" % (disp or "-", self.title[:40])

    def save(self, *args, **kwargs):
        if self.number == 0:
            max_n = Ticket.objects.aggregate(m=models.Max("number"))["m"] or 0
            self.number = max_n + 1
        super().save(*args, **kwargs)


class TicketTransitionLog(models.Model):
    ticket = models.ForeignKey(
        Ticket, on_delete=models.CASCADE, related_name="transitions", verbose_name="工单"
    )
    from_stage = models.CharField("来源阶段", max_length=32, blank=True)
    to_stage = models.CharField("目标阶段", max_length=32)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ticket_operations",
        verbose_name="操作人",
    )
    note = models.CharField("备注", max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def get_from_stage_display(self):
        if not self.from_stage:
            return ""
        try:
            return TicketStage(self.from_stage).label
        except ValueError:
            return self.from_stage

    def get_to_stage_display(self):
        try:
            return TicketStage(self.to_stage).label
        except ValueError:
            return self.to_stage

    class Meta:
        verbose_name = "阶段变更记录"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)
