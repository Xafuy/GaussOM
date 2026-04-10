from django.conf import settings
from django.db import models


class OnCallStatus(models.TextChoices):
    ONLINE = "online", "在线"
    BUSY = "busy", "忙碌"
    OFFLINE = "offline", "离线"


class RotaTable(models.Model):
    """工作日白天轮值表（可多张）"""

    name = models.CharField("名称", max_length=128)
    slug = models.SlugField("标识", max_length=64, unique=True)
    is_active = models.BooleanField("启用", default=True)
    description = models.CharField("说明", max_length=512, blank=True)

    class Meta:
        verbose_name = "轮值表"
        verbose_name_plural = verbose_name
        ordering = ("slug",)

    def __str__(self):
        return self.name


class RotaMember(models.Model):
    rota = models.ForeignKey(
        RotaTable, on_delete=models.CASCADE, related_name="members", verbose_name="轮值表"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="rota_memberships",
        verbose_name="成员",
    )
    sort_order = models.PositiveIntegerField("顺序", default=0)
    status = models.CharField(
        "当值状态",
        max_length=16,
        choices=OnCallStatus.choices,
        default=OnCallStatus.ONLINE,
    )
    # 负载等统计可由后续定时任务写入，先留简单计数
    active_ticket_count = models.PositiveIntegerField("进行中单据数", default=0)

    class Meta:
        verbose_name = "轮值成员"
        verbose_name_plural = verbose_name
        ordering = ("rota", "sort_order", "id")
        unique_together = ("rota", "user")

    def __str__(self):
        return "%s — %s" % (self.rota.slug, self.user_id)


class DutySheet(models.Model):
    """晚间/节假日值班表"""

    name = models.CharField("名称", max_length=128)
    slug = models.SlugField("标识", max_length=64, unique=True)
    is_active = models.BooleanField("启用", default=True)

    class Meta:
        verbose_name = "值班表"
        verbose_name_plural = verbose_name
        ordering = ("slug",)

    def __str__(self):
        return self.name


class DutyAssignment(models.Model):
    """某日某值班表上的值班人员（可多人在同一日）"""

    sheet = models.ForeignKey(
        DutySheet,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="值班表",
    )
    date = models.DateField("日期")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_assignments",
        verbose_name="值班人",
    )
    note = models.CharField("备注", max_length=256, blank=True)

    class Meta:
        verbose_name = "值班排班"
        verbose_name_plural = verbose_name
        ordering = ("date", "sheet_id", "user_id")

    def __str__(self):
        return "%s %s" % (self.date, self.sheet.slug)


class IdentityRouteRule(models.Model):
    class Identity(models.TextChoices):
        BU = "bu", "BU"
        CONTROL = "control", "管控"
        OPS = "ops", "运维"
        DEV = "dev", "开发"
        GUEST = "guest", "访客"
        HCS = "hcs", "HCS"

    class TimeWindow(models.TextChoices):
        DAY = "day", "工作日白天"
        NIGHT = "night", "晚间/节假日"

    identity = models.CharField("提单人身份", max_length=16, choices=Identity.choices)
    time_window = models.CharField("时间窗口", max_length=16, choices=TimeWindow.choices)
    rota_table = models.ForeignKey(
        RotaTable,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="identity_routes",
        verbose_name="命中轮值表",
    )
    duty_sheet = models.ForeignKey(
        DutySheet,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="identity_routes",
        verbose_name="命中值班表",
    )
    priority = models.PositiveIntegerField("优先级", default=100)
    is_active = models.BooleanField("启用", default=True)
    note = models.CharField("说明", max_length=255, blank=True)

    class Meta:
        verbose_name = "身份分单路由规则"
        verbose_name_plural = verbose_name
        ordering = ("priority", "id")
        unique_together = ("identity", "time_window", "priority")

    def __str__(self):
        return "%s-%s-%s" % (self.identity, self.time_window, self.priority)


class LeaveRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已驳回"

    applicant = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
        verbose_name="申请人",
    )
    leave_type = models.CharField("申请类型", max_length=64)
    start_at = models.DateTimeField("开始时间")
    end_at = models.DateTimeField("结束时间")
    reason = models.TextField("理由", blank=True)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PENDING
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_approvals",
        verbose_name="审批人",
    )
    cc = models.CharField("抄送说明", max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "请假申请"
        verbose_name_plural = verbose_name
        ordering = ("-created_at",)


class LeaveApproverConfig(models.Model):
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_approver_configs",
        verbose_name="审批人",
    )
    sort_order = models.PositiveIntegerField("排序", default=0)
    is_active = models.BooleanField("启用", default=True)
    note = models.CharField("说明", max_length=255, blank=True)

    class Meta:
        verbose_name = "请假审批人配置"
        verbose_name_plural = verbose_name
        ordering = ("sort_order", "id")
        unique_together = ("approver",)

    def __str__(self):
        return "%s" % (self.approver.get_full_name() or self.approver.username)
