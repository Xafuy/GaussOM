from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.contrib import messages
from django.shortcuts import redirect, render
import calendar
from datetime import datetime

from scheduling.models import (
    DutyAssignment,
    DutySheet,
    IdentityRouteRule,
    LeaveApproverConfig,
    LeaveRequest,
    RotaTable,
)
from rbac.services import can_create_ticket, can_join_duty_rota
from tickets.models import Ticket, TicketStage


@login_required
def home(request):
    my_pending = (
        Ticket.objects.select_related("reporter", "assignee")
        .filter(assignee=request.user)
        .exclude(stage=TicketStage.CLOSED)[:20]
    )
    return render(
        request,
        "portal/home.html",
        {
            "recent_tickets": my_pending,
            "can_create_ticket": can_create_ticket(request.user),
        },
    )


@login_required
def duty_overview(request):
    can_edit_schedule = request.user.is_staff or request.user.is_superuser
    can_apply_leave = bool(
        request.user.is_authenticated
        and (
            request.user.rota_memberships.exists()
            or request.user.duty_assignments.exists()
        )
    )
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
    try:
        edit_date_obj = datetime.strptime(edit_date, "%Y-%m-%d").date()
    except ValueError:
        edit_date_obj = today
        edit_date = str(today)
    user_qs = get_user_model().objects.filter(is_active=True).order_by("first_name", "username")
    active_users = (
        [u for u in user_qs if can_join_duty_rota(u)] if can_edit_schedule else []
    )

    if request.method == "POST":
        action = request.POST.get("action")
        redirect_url = request.path
        if selected_sheet:
            redirect_url = "%s?sheet=%s&date=%s" % (request.path, selected_sheet.id, edit_date)

        if action in {"save_day", "clear_day"}:
            if not selected_sheet:
                messages.error(request, "请先选择值班表")
                return redirect(request.path)
            if not can_edit_schedule:
                messages.error(request, "仅管理员可编辑值班与排班。")
                return redirect(redirect_url)
            edit_date = request.POST.get("edit_date") or edit_date
            selected_user_ids = request.POST.getlist("user_ids")
            try:
                date_obj = datetime.strptime(edit_date, "%Y-%m-%d").date()
            except ValueError:
                messages.error(request, "日期格式错误，请使用 YYYY-MM-DD")
                return redirect(redirect_url)
            if action == "clear_day":
                DutyAssignment.objects.filter(sheet=selected_sheet, date=date_obj).delete()
                messages.success(request, "已清空该日期值班安排")
                return redirect(redirect_url)
            DutyAssignment.objects.filter(sheet=selected_sheet, date=date_obj).exclude(
                user_id__in=selected_user_ids
            ).delete()
            User = get_user_model()
            for uid in selected_user_ids:
                u = User.objects.filter(pk=uid, is_active=True).first()
                if not u:
                    messages.error(request, "存在无效用户，请重新选择")
                    return redirect(redirect_url)
                if not can_join_duty_rota(u):
                    messages.error(
                        request,
                        "值班人员须同时具备「运维人员分析」「运维人员闭环」阶段权限：%s"
                        % u.username,
                    )
                    return redirect(redirect_url)
                DutyAssignment.objects.get_or_create(
                    sheet=selected_sheet, date=date_obj, user_id=uid
                )
            messages.success(request, "已保存该日期值班人员")
            return redirect(redirect_url)

        if action in {"leave_approve", "leave_reject"}:
            if not can_edit_schedule:
                messages.error(request, "仅管理员可审批请假。")
                return redirect(redirect_url)
            leave_id = request.POST.get("leave_id")
            leave = LeaveRequest.objects.filter(pk=leave_id).first()
            if not leave:
                messages.error(request, "请假记录不存在")
                return redirect(redirect_url)
            if leave.status != LeaveRequest.Status.PENDING:
                messages.error(request, "该请假已处理，请刷新页面")
                return redirect(redirect_url)
            if leave.approver_id and not (
                request.user.is_superuser or leave.approver_id == request.user.id
            ):
                messages.error(request, "该请假已指定审批人，当前账号不可审批")
                return redirect(redirect_url)
            leave.status = (
                LeaveRequest.Status.APPROVED
                if action == "leave_approve"
                else LeaveRequest.Status.REJECTED
            )
            if not leave.approver_id:
                leave.approver = request.user
            leave.save(update_fields=["status", "approver"])
            messages.success(
                request,
                "已%s该请假申请" % ("通过" if action == "leave_approve" else "驳回"),
            )
            return redirect(redirect_url)

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

    pending_leaves = []
    if can_edit_schedule:
        pending_leaves = (
            LeaveRequest.objects.select_related("applicant", "approver")
            .filter(status=LeaveRequest.Status.PENDING)
            .order_by("-created_at")[:30]
        )

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
            "can_apply_leave": can_apply_leave,
            "pending_leaves": pending_leaves,
        },
    )


@login_required
def leave_request(request):
    can_apply_leave = bool(
        request.user.is_authenticated
        and (
            request.user.rota_memberships.exists()
            or request.user.duty_assignments.exists()
        )
    )
    leave_approvers = (
        LeaveApproverConfig.objects.select_related("approver")
        .filter(is_active=True, approver__is_active=True)
        .order_by("sort_order", "id")
    )
    has_leave_approver = bool(leave_approvers)

    if request.method == "POST":
        if not can_apply_leave:
            messages.error(request, "仅轮值/值班人员可提交请假申请")
            return redirect("leave_request")
        leave_type = (request.POST.get("leave_type") or "").strip()
        start_raw = (request.POST.get("leave_start") or "").strip()
        end_raw = (request.POST.get("leave_end") or "").strip()
        reason = (request.POST.get("leave_reason") or "").strip()
        cc = (request.POST.get("leave_cc") or "").strip()
        approver_id = (request.POST.get("leave_approver_id") or "").strip()
        if not leave_type:
            messages.error(request, "请填写请假类型")
            return redirect("leave_request")
        if not approver_id:
            messages.error(request, "请选择审批人")
            return redirect("leave_request")
        approver_cfg = leave_approvers.filter(approver_id=approver_id).first()
        if not approver_cfg:
            messages.error(request, "审批人不在可配置名单中，请重新选择")
            return redirect("leave_request")
        try:
            start_at = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
            end_at = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            messages.error(request, "请假时间格式错误，请使用页面控件重新选择")
            return redirect("leave_request")
        if end_at <= start_at:
            messages.error(request, "结束时间必须晚于开始时间")
            return redirect("leave_request")
        LeaveRequest.objects.create(
            applicant=request.user,
            leave_type=leave_type,
            start_at=start_at,
            end_at=end_at,
            reason=reason,
            cc=cc,
            status=LeaveRequest.Status.PENDING,
            approver=approver_cfg.approver,
        )
        messages.success(request, "请假申请已提交，等待审批")
        return redirect("leave_request")

    my_leaves = (
        LeaveRequest.objects.select_related("approver")
        .filter(applicant=request.user)
        .order_by("-created_at")[:20]
    )
    return render(
        request,
        "portal/leave_request.html",
        {
            "can_apply_leave": can_apply_leave,
            "leave_approvers": leave_approvers,
            "has_leave_approver": has_leave_approver,
            "my_leaves": my_leaves,
        },
    )
