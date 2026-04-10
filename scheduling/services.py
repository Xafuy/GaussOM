from datetime import time

from django.utils import timezone

from .models import (
    DutyAssignment,
    LeaveRequest,
    OnCallStatus,
    RoleRouteRule,
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


def pick_assignee(when_dt=None, role_slugs=None):
    """
    基础分单：
    - 工作日白天：轮值表成员（在线/忙碌）
    - 其他时间：当天值班表成员
    - 一律跳过已审批请假人员
    """
    when_dt = when_dt or timezone.now()
    local = timezone.localtime(when_dt)
    is_workday_daytime = local.weekday() < 5 and WORK_START <= local.time() < WORK_END

    role_slugs = role_slugs or []
    route = _match_route_rule(is_workday_daytime, role_slugs)

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
        candidate_total = members.count()
        skipped_on_leave = 0
        for member in members:
            if not is_user_on_approved_leave(member.user, when_dt=when_dt):
                note = _route_observe_note(
                    mode="轮值",
                    is_daytime=True,
                    route=route,
                    role_slugs=role_slugs,
                    candidate_total=candidate_total,
                    skipped_on_leave=skipped_on_leave,
                )
                return member.user, note
            skipped_on_leave += 1
        return None, _route_observe_note(
            mode="轮值",
            is_daytime=True,
            route=route,
            role_slugs=role_slugs,
            candidate_total=candidate_total,
            skipped_on_leave=skipped_on_leave,
            failed=True,
        )

    assignments = (
        DutyAssignment.objects.select_related("user", "sheet")
        .filter(sheet__is_active=True, date=local.date(), user__is_active=True)
        .order_by("sheet_id", "id")
    )
    if route and route.duty_sheet_id:
        assignments = assignments.filter(sheet_id=route.duty_sheet_id)
    candidate_total = assignments.count()
    skipped_on_leave = 0
    for assignment in assignments:
        if not is_user_on_approved_leave(assignment.user, when_dt=when_dt):
            note = _route_observe_note(
                mode="值班",
                is_daytime=False,
                route=route,
                role_slugs=role_slugs,
                candidate_total=candidate_total,
                skipped_on_leave=skipped_on_leave,
            )
            return assignment.user, note
        skipped_on_leave += 1
    return None, _route_observe_note(
        mode="值班",
        is_daytime=False,
        route=route,
        role_slugs=role_slugs,
        candidate_total=candidate_total,
        skipped_on_leave=skipped_on_leave,
        failed=True,
    )


def _match_route_rule(is_daytime, role_slugs):
    window = RoleRouteRule.TimeWindow.DAY if is_daytime else RoleRouteRule.TimeWindow.NIGHT
    chain = [i.lower() for i in role_slugs if i]
    seen = set()
    for slug in chain:
        if slug in seen:
            continue
        seen.add(slug)
        rule = (
            RoleRouteRule.objects.select_related("role", "rota_table", "duty_sheet")
            .filter(
                role__slug=slug,
                time_window=window,
                is_active=True,
            )
            .order_by("priority", "id")
            .first()
        )
        if rule:
            return rule
    return None


def _route_observe_note(
    mode, is_daytime, route, role_slugs, candidate_total, skipped_on_leave, failed=False
):
    win = "day" if is_daytime else "night"
    role_part = ",".join([s for s in role_slugs if s]) or "-"
    if route:
        route_part = "rule#%s/%s/%s" % (route.id, route.role.slug, route.time_window)
    else:
        route_part = "rule#none"
    status = "无可用人员" if failed else "命中可派人"
    return "%s分单[%s] roles=%s %s candidates=%s leave_skipped=%s result=%s" % (
        mode,
        win,
        role_part,
        route_part,
        candidate_total,
        skipped_on_leave,
        status,
    )
