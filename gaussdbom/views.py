from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db import connection
from django.db.models import Count, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET

from apps.analytics.models import AdsStageFunnelDaily, AdsTicketKpiDaily
from apps.ticket.constants import STAGE_LABELS
from apps.ticket.models import Ticket, TicketTransition

User = get_user_model()


@require_GET
def healthz(request):
    """负载均衡存活探测：不访问数据库。"""
    return JsonResponse({"status": "ok", "service": "gaussdbom"})


@require_GET
def readyz(request):
    """就绪探测：校验数据库连接。"""
    try:
        connection.ensure_connection()
    except Exception as exc:
        return JsonResponse(
            {"status": "not_ready", "database": str(exc)},
            status=503,
        )
    return JsonResponse({"status": "ready", "database": "ok"})


def home(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required
def dashboard(request):
    by_stage = (
        Ticket.objects.filter(status=Ticket.TicketStatus.PROCESSING)
        .values("current_stage_code")
        .annotate(c=Count("id"))
        .order_by("-c")
    )
    stage_rows = [
        {
            "code": row["current_stage_code"],
            "label": STAGE_LABELS.get(
                row["current_stage_code"], row["current_stage_code"]
            ),
            "count": row["c"],
        }
        for row in by_stage
    ]
    recent = Ticket.objects.select_related("creator_user", "current_assignee").order_by(
        "-created_at"
    )[:10]

    assignee_rows = (
        User.objects.annotate(
            open_count=Count(
                "current_tickets",
                filter=Q(current_tickets__status=Ticket.TicketStatus.PROCESSING),
            )
        )
        .filter(open_count__gt=0)
        .order_by("-open_count")[:8]
    )

    kpi = AdsTicketKpiDaily.objects.order_by("-stat_date").first()
    funnel = list(
        AdsStageFunnelDaily.objects.order_by("-stat_date", "-transfer_count")[:12]
    )

    transition_trend = list(
        TicketTransition.objects.annotate(d=TruncDate("created_at"))
        .values("d")
        .annotate(c=Count("id"))
        .order_by("-d")[:14]
    )

    return render(
        request,
        "dashboard.html",
        {
            "stage_rows": stage_rows,
            "recent_tickets": recent,
            "assignee_rows": assignee_rows,
            "kpi_snapshot": kpi,
            "funnel_rows": funnel,
            "transition_trend": transition_trend,
        },
    )
