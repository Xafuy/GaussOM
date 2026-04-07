from django.conf import settings
from django.db import models


class DutyCalendar(models.Model):
    class DayType(models.TextChoices):
        WORKDAY = "workday", "工作日"
        WEEKEND = "weekend", "周末"
        HOLIDAY = "holiday", "法定节假日"

    class ShiftType(models.TextChoices):
        DAY = "day", "白班"
        NIGHT = "night", "夜班"

    calendar_date = models.DateField("日期", unique=True, db_index=True)
    day_type = models.CharField(
        "日类型", max_length=16, choices=DayType.choices, db_index=True
    )
    shift_type = models.CharField(
        "班次类型", max_length=16, choices=ShiftType.choices, default=ShiftType.DAY
    )

    class Meta:
        db_table = "duty_calendar"
        verbose_name = "值班日历"
        verbose_name_plural = verbose_name


class DutySchedule(models.Model):
    class ScheduleType(models.TextChoices):
        KERNEL = "kernel", "内核"
        CONTROL = "control", "管控"
        PUBLIC_CLOUD = "public_cloud", "公有云"
        SPECIAL = "special", "专项"

    class ApplicableDayType(models.TextChoices):
        WORKDAY = "workday", "工作日"
        NIGHT = "night", "夜班"
        HOLIDAY = "holiday", "节假日"
        ALL = "all", "全部"

    schedule_code = models.CharField("值班表编码", max_length=64, unique=True)
    schedule_name = models.CharField("值班表名称", max_length=128)
    schedule_type = models.CharField(
        "值班表类型", max_length=32, choices=ScheduleType.choices, db_index=True
    )
    applicable_day_type = models.CharField(
        "适用日类型", max_length=16, choices=ApplicableDayType.choices, default=ApplicableDayType.ALL
    )
    status = models.CharField(max_length=16, default="active", db_index=True)

    class Meta:
        db_table = "duty_schedule"
        verbose_name = "值班表"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.schedule_name


class DutyScheduleMember(models.Model):
    schedule = models.ForeignKey(
        DutySchedule, on_delete=models.CASCADE, related_name="members"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_schedule_memberships",
    )
    order_no = models.PositiveIntegerField("轮询顺序", default=0)
    weight = models.PositiveSmallIntegerField("权重", default=1)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "duty_schedule_member"
        unique_together = [("schedule", "user")]
        ordering = ["schedule_id", "order_no"]
        verbose_name = "值班成员"
        verbose_name_plural = verbose_name
        indexes = [
            models.Index(fields=["schedule", "order_no"]),
        ]


class LeaveRequest(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = "pending", "待审批"
        APPROVED = "approved", "已通过"
        REJECTED = "rejected", "已拒绝"
        CANCELLED = "cancelled", "已取消"

    applicant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type = models.CharField("请假类型", max_length=32, blank=True)
    start_time = models.DateTimeField("开始时间")
    end_time = models.DateTimeField("结束时间")
    reason = models.TextField("原因", blank=True)
    approval_status = models.CharField(
        "审批状态",
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "leave_request"
        verbose_name = "请假申请"
        verbose_name_plural = verbose_name


class LeaveApprovalRecord(models.Model):
    class Action(models.TextChoices):
        APPROVE = "approve", "通过"
        REJECT = "reject", "拒绝"

    leave_request = models.ForeignKey(
        LeaveRequest, on_delete=models.CASCADE, related_name="approval_records"
    )
    reviewer_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_approval_records",
    )
    action = models.CharField("动作", max_length=16, choices=Action.choices)
    comment = models.TextField("意见", blank=True)
    action_time = models.DateTimeField("操作时间", auto_now_add=True)

    class Meta:
        db_table = "leave_approval_record"
        verbose_name = "请假审批记录"
        verbose_name_plural = verbose_name


class DutySubstitution(models.Model):
    schedule = models.ForeignKey(
        DutySchedule, on_delete=models.CASCADE, related_name="substitutions"
    )
    from_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_substitutions_from",
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="duty_substitutions_to",
    )
    start_time = models.DateTimeField("开始时间")
    end_time = models.DateTimeField("结束时间")
    reason = models.TextField("原因", blank=True)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "duty_substitution"
        verbose_name = "调班/代班"
        verbose_name_plural = verbose_name
