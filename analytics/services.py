from datetime import datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from scheduling.models import LeaveRequest
from tickets.models import Ticket, TicketStage, TicketTransitionLog

SLA_HOURS = {"一般": 72, "严重": 24, "致命": 8, "事故": 4}


def parse_time_range(params):
    now = timezone.now()
    mode = (params.get("range") or "30d").strip()
    if mode in {"7d", "30d", "90d"}:
        days = int(mode.replace("d", ""))
        return now - timedelta(days=days), now, mode
    start = (params.get("start") or "").strip()
    end = (params.get("end") or "").strip()
    if start and end:
        try:
            start_dt = timezone.make_aware(
                datetime.combine(datetime.strptime(start, "%Y-%m-%d").date(), time.min)
            )
            end_dt = timezone.make_aware(
                datetime.combine(datetime.strptime(end, "%Y-%m-%d").date(), time.max)
            )
            return start_dt, end_dt, "custom"
        except ValueError:
            pass
    return now - timedelta(days=30), now, "30d"


def _field_from_ticket(ticket, keys):
    stage_fields = (ticket.extra_data or {}).get("stage_fields", {})
    for stage_map in stage_fields.values():
        if not isinstance(stage_map, dict):
            continue
        for key in keys:
            val = (stage_map.get(key) or "").strip() if isinstance(stage_map.get(key), str) else stage_map.get(key)
            if val:
                return str(val)
    return ""


def overview_metrics(start_dt, end_dt):
    qs = Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    total = qs.count()
    closed = qs.filter(stage=TicketStage.CLOSED).count()
    close_rate = round((closed * 100.0 / total), 2) if total else 0
    close_logs = (
        TicketTransitionLog.objects.filter(
            ticket__in=qs, to_stage=TicketStage.CLOSED
        )
        .order_by("ticket_id", "-created_at")
        .select_related("ticket")
    )
    latest_close = {}
    for lg in close_logs:
        latest_close.setdefault(lg.ticket_id, lg)
    durations = []
    for lg in latest_close.values():
        durations.append((lg.created_at - lg.ticket.created_at).total_seconds() / 3600.0)
    avg_close_hours = round(sum(durations) / len(durations), 2) if durations else 0
    overdue = 0
    for t in qs:
        sev = _field_from_ticket(t, ["severity"])
        target = SLA_HOURS.get(sev)
        if target and (timezone.now() - t.created_at).total_seconds() / 3600.0 > target:
            overdue += 1
    overdue_rate = round((overdue * 100.0 / total), 2) if total else 0
    return {
        "total": total,
        "closed": closed,
        "close_rate": close_rate,
        "avg_close_hours": avg_close_hours,
        "overdue_rate": overdue_rate,
    }


def manpower_metrics(start_dt, end_dt):
    tickets = (
        Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        .select_related("assignee")
        .all()
    )
    by_assignee = {}
    for t in tickets:
        if not t.assignee:
            continue
        name = (t.assignee.get_full_name() or "").strip() or t.assignee.username
        by_assignee[name] = by_assignee.get(name, 0) + 1
    transitions = (
        TicketTransitionLog.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        .values("operator__username")
        .annotate(cnt=Count("id"))
        .order_by("-cnt")
    )
    by_operator = [{"name": i["operator__username"] or "未知", "value": i["cnt"]} for i in transitions]
    return {
        "by_assignee": [{"name": k, "value": v} for k, v in sorted(by_assignee.items(), key=lambda x: x[1], reverse=True)],
        "by_operator": by_operator[:20],
    }


def collaboration_metrics(start_dt, end_dt):
    """
    协助口径：
    - 基于流转日志 operator 统计“协助过的工单数”（去重 ticket_id）
    - 排除仅创建动作（from_stage 为空）对协助次数的干扰
    """
    logs = TicketTransitionLog.objects.filter(
        created_at__gte=start_dt, created_at__lte=end_dt
    ).exclude(from_stage="")
    pairs = set()
    for lg in logs.values("operator__username", "ticket_id"):
        username = lg["operator__username"] or "未知"
        pairs.add((username, lg["ticket_id"]))
    counter = {}
    for username, _ in pairs:
        counter[username] = counter.get(username, 0) + 1
    top = [
        {"name": k, "value": v}
        for k, v in sorted(counter.items(), key=lambda x: x[1], reverse=True)[:20]
    ]
    return {"by_operator_distinct_tickets": top}


def ownership_metrics(start_dt, end_dt):
    tickets = Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    module = {}
    issue_type = {}
    severity = {}
    site = {}
    for t in tickets:
        m = _field_from_ticket(t, ["owned_module", "introduced_module"]) or "未填写"
        it = _field_from_ticket(t, ["issue_type", "issue_type_prejudge"]) or "未填写"
        sv = _field_from_ticket(t, ["severity"]) or "未填写"
        st = _field_from_ticket(t, ["site"]) or "未填写"
        module[m] = module.get(m, 0) + 1
        issue_type[it] = issue_type.get(it, 0) + 1
        severity[sv] = severity.get(sv, 0) + 1
        site[st] = site.get(st, 0) + 1
    def top_map(data):
        return [{"name": k, "value": v} for k, v in sorted(data.items(), key=lambda x: x[1], reverse=True)[:20]]
    return {"module": top_map(module), "issue_type": top_map(issue_type), "severity": top_map(severity), "site": top_map(site)}


def flow_metrics(start_dt, end_dt):
    logs = list(
        TicketTransitionLog.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
        .order_by("ticket_id", "created_at")
        .values("ticket_id", "from_stage", "to_stage", "created_at")
    )
    transition_counter = {}
    stage_enter = {}
    dwell = {}
    for lg in logs:
        key = "%s->%s" % (lg["from_stage"] or "start", lg["to_stage"])
        transition_counter[key] = transition_counter.get(key, 0) + 1
        tid = lg["ticket_id"]
        cur = lg["to_stage"]
        if tid in stage_enter:
            prev_stage, prev_time = stage_enter[tid]
            hours = (lg["created_at"] - prev_time).total_seconds() / 3600.0
            agg = dwell.setdefault(prev_stage, [])
            agg.append(hours)
        stage_enter[tid] = (cur, lg["created_at"])
    dwell_avg = [{"name": k, "value": round(sum(v) / len(v), 2)} for k, v in dwell.items() if v]
    transitions = [{"name": k, "value": v} for k, v in sorted(transition_counter.items(), key=lambda x: x[1], reverse=True)]
    return {"transitions": transitions, "dwell_avg_hours": dwell_avg}


def sla_trend_metrics(start_dt, end_dt):
    days = []
    cursor = start_dt.date()
    end_date = end_dt.date()
    while cursor <= end_date:
        days.append(cursor)
        cursor += timedelta(days=1)
    day_map = {d.strftime("%Y-%m-%d"): {"total": 0, "overdue": 0} for d in days}
    qs = Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    now = timezone.now()
    for t in qs:
        key = timezone.localtime(t.created_at).strftime("%Y-%m-%d")
        if key not in day_map:
            continue
        day_map[key]["total"] += 1
        sev = _field_from_ticket(t, ["severity"])
        target = SLA_HOURS.get(sev)
        if target and (now - t.created_at).total_seconds() / 3600.0 > target:
            day_map[key]["overdue"] += 1
    x = list(day_map.keys())
    total = [day_map[k]["total"] for k in x]
    overdue = [day_map[k]["overdue"] for k in x]
    return {"x": x, "total": total, "overdue": overdue}


def schedule_link_metrics(start_dt, end_dt):
    qs = Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    day_cnt = 0
    night_cnt = 0
    leave_overlap = 0
    for t in qs:
        local = timezone.localtime(t.created_at)
        if 9 <= local.hour < 18:
            day_cnt += 1
        else:
            night_cnt += 1
        if t.assignee and LeaveRequest.objects.filter(
            applicant=t.assignee,
            status=LeaveRequest.Status.APPROVED,
            start_at__lte=t.created_at,
            end_at__gte=t.created_at,
        ).exists():
            leave_overlap += 1
    return {
        "day_night": [
            {"name": "白天分单", "value": day_cnt},
            {"name": "夜间/节假日分单", "value": night_cnt},
        ],
        "leave_overlap": leave_overlap,
    }


def efficiency_metrics(start_dt, end_dt):
    """
    运维效率分析：
    - 模块SLA：按模块统计在SLA内关闭率（仅统计窗口内关闭）
    - 人员SLA：按关单操作人统计在SLA内关闭率（仅统计窗口内关闭）
    - 运维人员独立问题闭环率：进入运维分析且未进入开发阶段的工单，最终关闭占比
    - 开发人员问题闭环率：进入开发阶段的工单，最终关闭占比
    """
    closed_logs = (
        TicketTransitionLog.objects.filter(
            to_stage=TicketStage.CLOSED,
            created_at__gte=start_dt,
            created_at__lte=end_dt,
        )
        .select_related("ticket", "operator")
        .order_by("ticket_id", "-created_at")
    )
    latest_close = {}
    for lg in closed_logs:
        latest_close.setdefault(lg.ticket_id, lg)

    module_counter = {}
    person_counter = {}
    for lg in latest_close.values():
        t = lg.ticket
        sev = _field_from_ticket(t, ["severity"])
        target = SLA_HOURS.get(sev)
        if not target:
            continue
        hours = (lg.created_at - t.created_at).total_seconds() / 3600.0
        in_sla = hours <= target

        module = _field_from_ticket(t, ["owned_module", "introduced_module"]) or "未填写"
        mod = module_counter.setdefault(module, {"total": 0, "in_sla": 0})
        mod["total"] += 1
        if in_sla:
            mod["in_sla"] += 1

        person = (
            (lg.operator.get_full_name() or "").strip() or lg.operator.username
            if lg.operator
            else "未知"
        )
        psn = person_counter.setdefault(person, {"total": 0, "in_sla": 0})
        psn["total"] += 1
        if in_sla:
            psn["in_sla"] += 1

    def to_rate_rows(counter):
        rows = []
        for name, d in counter.items():
            rate = round((d["in_sla"] * 100.0 / d["total"]), 2) if d["total"] else 0
            rows.append({"name": name, "value": rate, "total": d["total"]})
        rows.sort(key=lambda x: (x["value"], x["total"]), reverse=True)
        return rows[:20]

    tickets = Ticket.objects.filter(created_at__gte=start_dt, created_at__lte=end_dt)
    independent_total = 0
    independent_closed = 0
    dev_total = 0
    dev_closed = 0
    for t in tickets:
        logs = list(t.transitions.values_list("to_stage", flat=True))
        entered_ops = TicketStage.OPS_ANALYSIS in logs or t.stage == TicketStage.OPS_ANALYSIS
        entered_dev = (
            TicketStage.DEV_ANALYSIS in logs
            or TicketStage.DEV_REVIEW in logs
            or t.stage in {TicketStage.DEV_ANALYSIS, TicketStage.DEV_REVIEW}
        )
        is_closed = t.stage == TicketStage.CLOSED or TicketStage.CLOSED in logs
        if entered_ops and not entered_dev:
            independent_total += 1
            if is_closed:
                independent_closed += 1
        if entered_dev:
            dev_total += 1
            if is_closed:
                dev_closed += 1

    independent_rate = (
        round(independent_closed * 100.0 / independent_total, 2)
        if independent_total
        else 0
    )
    dev_close_rate = round(dev_closed * 100.0 / dev_total, 2) if dev_total else 0

    return {
        "module_sla_rate": to_rate_rows(module_counter),
        "person_sla_rate": to_rate_rows(person_counter),
        "ops_independent_close_rate": independent_rate,
        "ops_independent_total": independent_total,
        "ops_independent_closed": independent_closed,
        "dev_close_rate": dev_close_rate,
        "dev_total": dev_total,
        "dev_closed": dev_closed,
    }
