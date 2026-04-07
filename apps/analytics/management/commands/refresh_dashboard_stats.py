from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from apps.analytics.models import AdsStageFunnelDaily, AdsTicketKpiDaily
from apps.ticket.models import Ticket, TicketTransition


class Command(BaseCommand):
    help = "从工单明细刷新日级 KPI 与阶段漏斗快照（SQLite 轻量版）。"

    def handle(self, *args, **options):
        today = timezone.localdate()
        self._rollup_kpi(today)
        self._rollup_funnel(today)
        self.stdout.write(self.style.SUCCESS(f"已刷新 {today} 及近期汇总。"))

    def _rollup_kpi(self, today):
        qs = Ticket.objects.filter(created_at__date=today)
        total = qs.count()
        closed = qs.filter(status=Ticket.TicketStatus.CLOSED).count()
        sla = closed
        avg_min = None
        closed_qs = qs.filter(
            status=Ticket.TicketStatus.CLOSED, closed_at__isnull=False
        )
        deltas = []
        for t in closed_qs:
            delta = (t.closed_at - t.opened_at).total_seconds() / 60
            if delta >= 0:
                deltas.append(delta)
        if deltas:
            avg_min = int(sum(deltas) / len(deltas))

        row = AdsTicketKpiDaily.objects.filter(
            stat_date=today, group__isnull=True, user__isnull=True
        ).first()
        if row:
            row.ticket_count = total
            row.closed_count = closed
            row.sla_ontime_count = sla
            row.avg_close_minutes = avg_min
            row.save(
                update_fields=[
                    "ticket_count",
                    "closed_count",
                    "sla_ontime_count",
                    "avg_close_minutes",
                ]
            )
        else:
            AdsTicketKpiDaily.objects.create(
                stat_date=today,
                group=None,
                user=None,
                ticket_count=total,
                closed_count=closed,
                sla_ontime_count=sla,
                avg_close_minutes=avg_min,
            )

    def _rollup_funnel(self, today):
        start = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        end = start + timedelta(days=1)
        pairs = (
            TicketTransition.objects.filter(created_at__gte=start, created_at__lt=end)
            .exclude(from_stage_code="")
            .values("from_stage_code", "to_stage_code")
            .annotate(c=Count("id"))
        )
        total_moves = sum(p["c"] for p in pairs) or 1
        AdsStageFunnelDaily.objects.filter(stat_date=today).delete()
        for row in pairs:
            AdsStageFunnelDaily.objects.create(
                stat_date=today,
                from_stage_code=row["from_stage_code"],
                to_stage_code=row["to_stage_code"],
                transfer_count=row["c"],
                transfer_ratio=round(row["c"] / total_moves, 6),
            )
