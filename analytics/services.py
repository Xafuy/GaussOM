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
    closed = qs.filter(stage=TicketStage.AUDIT_CLOSE).count()
    close_rate = round((closed * 100.0 / total), 2) if total else 0
    close_logs = (
        TicketTransitionLog.objects.filter(
            ticket__in=qs, to_stage=TicketStage.AUDIT_CLOSE
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
