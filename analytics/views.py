from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import render

from rbac.services import has_permission

from .services import (
    flow_metrics,
    manpower_metrics,
    overview_metrics,
    ownership_metrics,
    parse_time_range,
    schedule_link_metrics,
    sla_trend_metrics,
)


def _can_view_dashboard(user):
    return bool(user.is_authenticated and has_permission(user, "dashboard:view"))


@login_required
@user_passes_test(_can_view_dashboard)
def dashboard(request):
    start_dt, end_dt, mode = parse_time_range(request.GET)
    payload = {
        "overview": overview_metrics(start_dt, end_dt),
        "manpower": manpower_metrics(start_dt, end_dt),
        "ownership": ownership_metrics(start_dt, end_dt),
        "flow": flow_metrics(start_dt, end_dt),
        "sla": sla_trend_metrics(start_dt, end_dt),
        "schedule": schedule_link_metrics(start_dt, end_dt),
        "range_mode": mode,
        "start": start_dt.strftime("%Y-%m-%d"),
        "end": end_dt.strftime("%Y-%m-%d"),
    }
    return render(request, "analytics/dashboard.html", {"dashboard_data": payload})


@login_required
@user_passes_test(_can_view_dashboard)
def dashboard_api(request):
    start_dt, end_dt, mode = parse_time_range(request.GET)
    payload = {
        "overview": overview_metrics(start_dt, end_dt),
        "manpower": manpower_metrics(start_dt, end_dt),
        "ownership": ownership_metrics(start_dt, end_dt),
        "flow": flow_metrics(start_dt, end_dt),
        "sla": sla_trend_metrics(start_dt, end_dt),
        "schedule": schedule_link_metrics(start_dt, end_dt),
        "range_mode": mode,
        "start": start_dt.strftime("%Y-%m-%d"),
        "end": end_dt.strftime("%Y-%m-%d"),
    }
    return JsonResponse(payload)
