from datetime import time

from django.utils import timezone

from .models import (
    DutyAssignment,
    IdentityRouteRule,
    LeaveRequest,
    OnCallStatus,
    RotaMember,
)


WORK_START = time(9, 0)
WORK_END = time(18, 0)


def is_user_on_approved_leave(user, when_dt=None):
    when_dt = when_dt or timezone.now()
    return LeaveRequest.objects.filter(
        applicant=user,
        status=LeaveRequest.Status.APPROVED,
        start_at__lte=when_dt,
        end_at__gte=when_dt,
    ).exists()


def pick_assignee(when_dt=None, identities=None):
    """
    基础分单：
    - 工作日白天：轮值表成员（在线/忙碌）
    - 其他时间：当天值班表成员
    - 一律跳过已审批请假人员
    """
    when_dt = when_dt or timezone.now()
    local = timezone.localtime(when_dt)
    is_workday_daytime = local.weekday() < 5 and WORK_START <= local.time() < WORK_END

    identities = identities or []
    route = _match_route_rule(is_workday_daytime, identities)

    if is_workday_daytime:
        members = (
            RotaMember.objects.select_related("user", "rota")
            .filter(
                rota__is_active=True,
                user__is_active=True,
                status__in=[OnCallStatus.ONLINE, OnCallStatus.BUSY],
            )
            .order_by("active_ticket_count", "sort_order", "id")
        )
        if route and route.rota_table_id:
            members = members.filter(rota_id=route.rota_table_id)
        for member in members:
            if not is_user_on_approved_leave(member.user, when_dt=when_dt):
                note = "轮值表自动分配（工作日白天）"
                if route and route.rota_table:
                    note += "，命中路由表:%s" % route.rota_table.slug
                return member.user, note
        return None, "轮值表无可用人员"

    assignments = (
        DutyAssignment.objects.select_related("user", "sheet")
        .filter(sheet__is_active=True, date=local.date(), user__is_active=True)
        .order_by("sheet_id", "id")
    )
    if route and route.duty_sheet_id:
        assignments = assignments.filter(sheet_id=route.duty_sheet_id)
    for assignment in assignments:
        if not is_user_on_approved_leave(assignment.user, when_dt=when_dt):
            note = "值班表自动分配（晚间/节假日）"
            if route and route.duty_sheet:
                note += "，命中路由表:%s" % route.duty_sheet.slug
            return assignment.user, note
    return None, "值班表无可用人员"


def _match_route_rule(is_daytime, identities):
    window = (
        IdentityRouteRule.TimeWindow.DAY
        if is_daytime
        else IdentityRouteRule.TimeWindow.NIGHT
    )
    chain = [i.lower() for i in identities if i] + ["hcs", "guest"]
    seen = set()
    for identity in chain:
        if identity in seen:
            continue
        seen.add(identity)
        rule = (
            IdentityRouteRule.objects.select_related("rota_table", "duty_sheet")
            .filter(
                identity=identity,
                time_window=window,
                is_active=True,
            )
            .order_by("priority", "id")
            .first()
        )
        if rule:
            return rule
    return None
