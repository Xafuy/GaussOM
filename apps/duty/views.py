from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Q
from django.views.generic import ListView

from apps.duty.models import DutySchedule


class DutyScheduleListView(LoginRequiredMixin, ListView):
    model = DutySchedule
    template_name = "duty/schedule_list.html"
    context_object_name = "schedules"

    def get_queryset(self):
        return (
            DutySchedule.objects.annotate(
                active_members=Count(
                    "members", filter=Q(members__status="active")
                )
            )
            .order_by("schedule_type", "id")
        )
