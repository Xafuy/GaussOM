from django.contrib import admin

from apps.analytics.models import AdsStageFunnelDaily, AdsTicketKpiDaily


@admin.register(AdsTicketKpiDaily)
class AdsTicketKpiDailyAdmin(admin.ModelAdmin):
    list_display = (
        "stat_date",
        "group",
        "user",
        "ticket_count",
        "closed_count",
        "sla_ontime_count",
        "avg_close_minutes",
    )
    list_filter = ("stat_date",)


@admin.register(AdsStageFunnelDaily)
class AdsStageFunnelDailyAdmin(admin.ModelAdmin):
    list_display = (
        "stat_date",
        "from_stage_code",
        "to_stage_code",
        "transfer_count",
        "transfer_ratio",
    )
    list_filter = ("stat_date",)
