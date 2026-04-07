from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.form.models import TicketFieldValue
from apps.form.services import (
    bindings_for_stage,
    get_field_values_map,
    get_published_schema,
    options_for_field,
    validate_and_save_stage,
)
from apps.ticket.constants import STAGE_LABELS
from apps.ticket.forms import TicketCreateForm
from apps.ticket.models import Ticket
from apps.ticket.workflow import (
    allowed_actions,
    apply_transition,
    create_ticket_initial,
    user_can_operate_ticket,
)

User = get_user_model()


class TicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "ticket/ticket_list.html"
    context_object_name = "tickets"
    paginate_by = 20

    def get_queryset(self):
        qs = Ticket.objects.select_related(
            "creator_user", "current_assignee"
        ).order_by("-created_at")
        q = self.request.GET.get("q", "").strip()
        st = self.request.GET.get("status", "").strip()
        if q:
            qs = qs.filter(
                Q(ticket_no__icontains=q)
                | Q(creator_user__username__icontains=q)
                | Q(current_assignee__username__icontains=q)
            )
        if st in (Ticket.TicketStatus.PROCESSING, Ticket.TicketStatus.CLOSED):
            qs = qs.filter(status=st)
        return qs


class TicketCreateView(LoginRequiredMixin, View):
    template_name = "ticket/ticket_create.html"

    def get(self, request):
        return render(request, self.template_name, {"form": TicketCreateForm()})

    def post(self, request):
        form = TicketCreateForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {"form": form})
        ticket = create_ticket_initial(
            creator=request.user,
            source_type=form.cleaned_data["source_type"],
            issue_type=form.cleaned_data.get("issue_type") or "",
        )
        TicketFieldValue.objects.update_or_create(
            ticket=ticket,
            stage_code=ticket.current_stage_code,
            field_code="ticket_description",
            defaults={
                "field_value_text": form.cleaned_data["description"],
                "updated_by": request.user,
            },
        )
        post = request.POST.copy()
        post["f_ticket_description"] = form.cleaned_data["description"]
        ok, errs = validate_and_save_stage(
            ticket,
            ticket.current_stage_code,
            post,
            request.user,
        )
        if not ok:
            ticket.delete()
            for e in errs:
                form.add_error(None, e)
            return render(request, self.template_name, {"form": form})
        messages.success(request, f"工单已创建：{ticket.ticket_no}")
        return redirect("ticket_detail", pk=ticket.pk)


class TicketDetailView(LoginRequiredMixin, View):
    template_name = "ticket/ticket_detail.html"

    def get(self, request, pk):
        ticket = get_object_or_404(
            Ticket.objects.select_related("creator_user", "current_assignee"), pk=pk
        )
        if not user_can_operate_ticket(ticket, request.user):
            messages.error(request, "无权查看该工单。")
            return redirect("ticket_list")
        schema = get_published_schema()
        bindings = []
        if schema:
            bindings = list(bindings_for_stage(schema, ticket.current_stage_code))
        values = get_field_values_map(ticket, ticket.current_stage_code)
        field_rows = []
        for b in bindings:
            field_rows.append(
                {
                    "binding": b,
                    "field": b.field,
                    "value": values.get(b.field.field_code, ""),
                    "options": options_for_field(b.field),
                }
            )
        actions = allowed_actions(ticket)
        users = User.objects.filter(is_active=True).order_by("username")[:500]
        transitions = ticket.transitions.select_related("operator_user").order_by(
            "-created_at"
        )[:50]
        return render(
            request,
            self.template_name,
            {
                "ticket": ticket,
                "stage_label": STAGE_LABELS.get(
                    ticket.current_stage_code, ticket.current_stage_code
                ),
                "field_rows": field_rows,
                "actions": actions,
                "users": users,
                "transitions": transitions,
                "can_operate": user_can_operate_ticket(ticket, request.user),
            },
        )

    def post(self, request, pk):
        ticket = get_object_or_404(Ticket, pk=pk)
        if not user_can_operate_ticket(ticket, request.user):
            messages.error(request, "无权操作该工单。")
            return redirect("ticket_list")

        if "save_fields" in request.POST:
            ok, errs = validate_and_save_stage(
                ticket, ticket.current_stage_code, request.POST, request.user
            )
            if ok:
                messages.success(request, "字段已保存。")
            else:
                for e in errs:
                    messages.error(request, e)
            return redirect("ticket_detail", pk=pk)

        action = request.POST.get("action_code", "").strip()
        comment = request.POST.get("comment", "").strip()
        target_user_id = request.POST.get("target_user_id") or None
        tid = int(target_user_id) if target_user_id and target_user_id.isdigit() else None
        ok, msg = apply_transition(
            ticket,
            request.user,
            action,
            comment=comment,
            target_user_id=tid,
        )
        if ok:
            messages.success(request, msg)
        else:
            messages.error(request, msg)
        return redirect("ticket_detail", pk=pk)
