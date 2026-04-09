from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
import calendar

from scheduling.models import (
    DutyAssignment,
    DutySheet,
    IdentityRouteRule,
    LeaveRequest,
    RotaTable,
)
from tickets.models import Ticket, TicketStage


@login_required
def home(request):
    my_pending = (
        Ticket.objects.select_related("reporter", "assignee")
        .filter(assignee=request.user)
        .exclude(stage=TicketStage.AUDIT_CLOSE)[:20]
    )
    return render(request, "portal/home.html", {"recent_tickets": my_pending})


@login_required
def duty_overview(request):
    can_edit_schedule = request.user.is_staff or request.user.is_superuser
    rota_tables = RotaTable.objects.prefetch_related("members__user").filter(is_active=True)
    from django.utils import timezone

    today = timezone.localdate()
    today_assignments = (
        DutyAssignment.objects.select_related("sheet", "user")
        .filter(date=today, sheet__is_active=True)
        .order_by("sheet__name", "id")
    )
    leaves = (
        LeaveRequest.objects.select_related("applicant", "approver")
        .filter(status=LeaveRequest.Status.APPROVED)
        .order_by("-start_at")[:20]
    )
    sheets = DutySheet.objects.filter(is_active=True).order_by("name")
    selected_sheet_id = request.GET.get("sheet")
    selected_sheet = None
    if selected_sheet_id:
        selected_sheet = sheets.filter(id=selected_sheet_id).first()
    if not selected_sheet:
        selected_sheet = sheets.first()

    edit_date = request.GET.get("date") or str(today)
    from datetime import datetime
    try:
        edit_date_obj = datetime.strptime(edit_date, "%Y-%m-%d").date()
    except ValueError:
        edit_date_obj = today
        edit_date = str(today)
    active_users = get_user_model().objects.filter(is_active=True).order_by("first_name", "username")

    if request.method == "POST" and selected_sheet:
        if not can_edit_schedule:
            messages.error(request, "仅管理员可编辑值班与排班。")
            return redirect("%s?sheet=%s&date=%s" % (request.path, selected_sheet.id, edit_date))
        action = request.POST.get("action")
        edit_date = request.POST.get("edit_date") or edit_date
        selected_user_ids = request.POST.getlist("user_ids")
        try:
            date_obj = datetime.strptime(edit_date, "%Y-%m-%d").date()
        except ValueError:
            messages.error(request, "日期格式错误，请使用 YYYY-MM-DD")
            return redirect("%s?sheet=%s&date=%s" % (request.path, selected_sheet.id, edit_date))

        if action == "clear_day":
            DutyAssignment.objects.filter(sheet=selected_sheet, date=date_obj).delete()
            messages.success(request, "已清空该日期值班安排")
            return redirect("%s?sheet=%s&date=%s" % (request.path, selected_sheet.id, edit_date))

        # save_day
        DutyAssignment.objects.filter(sheet=selected_sheet, date=date_obj).exclude(
            user_id__in=selected_user_ids
        ).delete()
        for uid in selected_user_ids:
            DutyAssignment.objects.get_or_create(
                sheet=selected_sheet, date=date_obj, user_id=uid
            )
        messages.success(request, "已保存该日期值班人员")
        return redirect("%s?sheet=%s&date=%s" % (request.path, selected_sheet.id, edit_date))

    cal_rows = []
    month_label = ""
    if selected_sheet:
        year = today.year
        month = today.month
        month_dates = calendar.Calendar(firstweekday=0).monthdatescalendar(year, month)
        month_label = "%04d-%02d" % (year, month)
        by_day = {}
        q = (
            DutyAssignment.objects.select_related("user")
            .filter(sheet=selected_sheet, date__year=year, date__month=month)
            .order_by("id")
        )
        for it in q:
            by_day.setdefault(it.date, []).append(
                (it.user.get_full_name() or it.user.username).strip()
            )

        for week in month_dates:
            line = []
            for d in week:
                line.append(
                    {
                        "date": d,
                        "in_month": d.month == month,
                        "is_today": d == today,
                        "names": by_day.get(d, []),
                    }
                )
            cal_rows.append(line)
    rules = (
        IdentityRouteRule.objects.select_related("rota_table", "duty_sheet")
        .filter(is_active=True)
        .order_by("identity", "time_window", "priority")
    )
    selected_user_ids_for_date = []
    if selected_sheet:
        selected_user_ids_for_date = [
            str(x.user_id)
            for x in DutyAssignment.objects.filter(sheet=selected_sheet, date=edit_date_obj)
        ]

    return render(
        request,
        "portal/duty.html",
        {
            "rota_tables": rota_tables,
            "today_assignments": today_assignments,
            "approved_leaves": leaves,
            "duty_sheets": sheets,
            "today": today,
            "route_rules": rules,
            "selected_sheet": selected_sheet,
            "month_label": month_label,
            "calendar_rows": cal_rows,
            "edit_date": edit_date,
            "active_users": active_users,
            "selected_user_ids_for_date": selected_user_ids_for_date,
            "can_edit_schedule": can_edit_schedule,
        },
    )
