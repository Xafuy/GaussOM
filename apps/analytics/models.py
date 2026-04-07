from django.conf import settings
from django.db import models


class AdsTicketKpiDaily(models.Model):
    stat_date = models.DateField("统计日期", db_index=True)
    group = models.ForeignKey(
        "system.SysOrgGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="ads_ticket_kpi_daily",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="ads_ticket_kpi_daily",
    )
    ticket_count = models.PositiveIntegerField("工单数", default=0)
    closed_count = models.PositiveIntegerField("关闭数", default=0)
    sla_ontime_count = models.PositiveIntegerField("SLA准时数", default=0)
    avg_close_minutes = models.PositiveIntegerField("平均闭环分钟", null=True, blank=True)

    class Meta:
        db_table = "ads_ticket_kpi_daily"
        unique_together = [("stat_date", "group", "user")]
        verbose_name = "工单KPI日汇总"
        verbose_name_plural = verbose_name


class AdsStageFunnelDaily(models.Model):
    stat_date = models.DateField("统计日期", db_index=True)
    from_stage_code = models.CharField("来源阶段", max_length=64, db_index=True)
    to_stage_code = models.CharField("目标阶段", max_length=64, db_index=True)
    transfer_count = models.PositiveIntegerField("流转次数", default=0)
    transfer_ratio = models.DecimalField(
        "流转比例", max_digits=7, decimal_places=4, null=True, blank=True
    )

    class Meta:
        db_table = "ads_stage_funnel_daily"
        verbose_name = "阶段漏斗日汇总"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["stat_date", "from_stage_code", "to_stage_code"]),
        ]
