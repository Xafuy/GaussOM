from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from rbac.services import can_create_ticket, can_handle_stage
from scheduling.services import pick_assignee

from .models import Ticket, TicketStage, TicketTransitionLog
from .stage_fields import get_field_defs_for_stage, get_module_tree


def _assignee_stage_map_get(ticket):
    return ((ticket.extra_data or {}).get("meta") or {}).get("assignee_by_stage") or {}


def _assignee_stage_map_write(ticket, stage, user_id):
    extra = ticket.extra_data or {}
    meta = extra.setdefault("meta", {})
    m = meta.setdefault("assignee_by_stage", {})
    m[stage] = user_id
    extra["meta"] = meta
    ticket.extra_data = extra


def _should_duty_pick_for_ops(entry_from_stage, next_stage):
    """进入运维分析且由值班分单：问题审核 → 运维分析，或 HCS 提单选「运维自提单」路径。"""
    if next_stage != TicketStage.OPS_ANALYSIS:
        return False
    return entry_from_stage in (
        TicketStage.ISSUE_REVIEW,
        TicketStage.HCS_SUBMIT,
    )


@login_required
def ticket_list(request):
    view_mode = request.GET.get("view", "mine")
    stage_filter = request.GET.get("stage", "")
    keyword = (request.GET.get("q") or "").strip()

    qs = Ticket.objects.select_related("reporter", "assignee").all()
    if view_mode == "mine":
        # 默认：需要我处理且尚未关闭
        qs = qs.filter(assignee=request.user).exclude(stage=TicketStage.CLOSED)
    elif view_mode == "created":
        qs = qs.filter(reporter=request.user)
    elif view_mode == "assisted":
        assisted_ids = (
            TicketTransitionLog.objects.filter(operator=request.user)
            .values_list("ticket_id", flat=True)
            .distinct()
        )
        qs = qs.filter(pk__in=assisted_ids)
    else:
        view_mode = "all"

    if stage_filter and stage_filter in dict(TicketStage.choices):
        qs = qs.filter(stage=stage_filter)

    if keyword:
        qs = qs.filter(Q(title__icontains=keyword) | Q(description__icontains=keyword))

    qs = qs[:200]
    rows = [_build_ticket_list_row(t) for t in qs]
    return render(
        request,
        "tickets/list.html",
        {
            "tickets": rows,
            "view_mode": view_mode,
            "stage_filter": stage_filter,
            "keyword": keyword,
            "stage_choices": TicketStage.choices,
            "can_create_ticket": can_create_ticket(request.user),
        },
    )


@login_required
def ticket_detail(request, pk):
    ticket = get_object_or_404(
        Ticket.objects.select_related("reporter", "assignee"), pk=pk
    )
    submit_source = _get_submit_source(ticket)
    if request.method == "POST":
        action = request.POST.get("action")
        stage_has_disposition_flow = ticket.stage in DISPOSITION_STAGE_MAP
        if action == "advance":
            advance_choice = (request.POST.get("advance_choice") or "").strip()
            next_assignee_raw = (request.POST.get("next_assignee_id") or "").strip()
            next_assignee_id = None
            if next_assignee_raw.isdigit():
                next_assignee_id = int(next_assignee_raw)
            if _can_operate_ticket(request.user, ticket) and can_handle_stage(
                request.user, ticket.stage
            ):
                _update_stage_fields(
                    ticket=ticket,
                    stage=ticket.stage,
                    post=request.POST,
                    submit_source=submit_source,
                )
                ok, msg = _advance_ticket(
                    ticket=ticket,
                    operator=request.user,
                    advance_choice=advance_choice,
                    next_assignee_id=next_assignee_id,
                )
                if ok:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                messages.error(request, "无权限推进（须为当前阶段处理人且具备本阶段权限）")
        elif action == "transfer":
            if ticket.stage == TicketStage.CLOSED:
                messages.error(request, "问题单关闭状态不可再转派")
                return redirect("ticket_detail", pk=ticket.pk)
            if stage_has_disposition_flow:
                messages.error(request, "当前阶段请通过“处理方式”完成处理人与流转，不支持独立转派")
                return redirect("ticket_detail", pk=ticket.pk)
            assignee_id = request.POST.get("assignee_id")
            assignee_query = (request.POST.get("assignee_query") or "").strip()
            if _can_operate_ticket(request.user, ticket) and can_handle_stage(
                request.user, ticket.stage
            ):
                ok, msg = _transfer_ticket(
                    ticket=ticket,
                    operator=request.user,
                    assignee_id=assignee_id,
                    assignee_query=assignee_query,
                )
                if ok:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                messages.error(request, "无权限转派（须为当前阶段处理人且具备本阶段权限）")
        elif action == "update_fields":
            if _can_operate_ticket(request.user, ticket) and can_handle_stage(
                request.user, ticket.stage
            ):
                changed_labels = _update_stage_fields(
                    ticket=ticket,
                    stage=ticket.stage,
                    post=request.POST,
                    submit_source=submit_source,
                )
                if changed_labels:
                    TicketTransitionLog.objects.create(
                        ticket=ticket,
                        from_stage=ticket.stage,
                        to_stage=ticket.stage,
                        operator=request.user,
                        note="更新详细信息: %s" % "、".join(changed_labels[:12]),
                    )
                messages.success(request, "详细信息已保存")
            else:
                messages.error(request, "无权限保存详细信息（须为当前阶段处理人且具备本阶段权限）")
        elif action == "rollback":
            if ticket.stage == TicketStage.CLOSED:
                messages.error(request, "问题单关闭状态不可再回退")
                return redirect("ticket_detail", pk=ticket.pk)
            if stage_has_disposition_flow:
                messages.error(request, "当前阶段请通过“处理方式”完成回退，不支持独立回退")
                return redirect("ticket_detail", pk=ticket.pk)
            reason = (request.POST.get("rollback_reason") or "").strip()
            if _can_operate_ticket(request.user, ticket) and can_handle_stage(
                request.user, ticket.stage
            ):
                ok, msg = _rollback_ticket(
                    ticket=ticket, operator=request.user, reason=reason
                )
                if ok:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                messages.error(request, "无权限回退（须为当前阶段处理人且具备本阶段权限）")
        elif action == "revoke":
            if (
                ticket.stage == TicketStage.HCS_SUBMIT
                and _can_operate_ticket(request.user, ticket)
                and can_handle_stage(request.user, ticket.stage)
            ):
                ok, msg = _revoke_ticket(ticket=ticket, operator=request.user)
                if ok:
                    messages.success(request, msg)
                    return redirect("ticket_list")
                messages.error(request, msg)
            else:
                messages.error(request, "仅HCS提单阶段当前处理人可撤销")
        return redirect("ticket_detail", pk=ticket.pk)

    logs = ticket.transitions.select_related("operator")[:50]
    users = [
        u
        for u in get_user_model().objects.filter(is_active=True).order_by("username")[:300]
        if can_handle_stage(u, ticket.stage)
    ]
    advance_options = _advance_options(ticket)
    stage_has_disposition_flow = ticket.stage in DISPOSITION_STAGE_MAP
    prev_stage = _previous_stage_of(ticket.stage)
    prev_stage_label = dict(TicketStage.choices).get(prev_stage, "")
    stage_field_defs = get_field_defs_for_stage(
        ticket.stage, context={"submit_source": submit_source}
    )
    stage_field_values = _get_stage_values(ticket, ticket.stage)
    all_values = _all_stage_values(ticket)
    stage_form_rows = []
    module_tree = get_module_tree()
    for fd in stage_field_defs:
        if fd["key"] == "disposition":
            continue
        if not _is_field_visible(fd, all_values):
            continue
        value = stage_field_values.get(fd["key"], "") or all_values.get(fd["key"], "")
        selected_values = []
        if fd.get("widget") == "user_multi_select":
            raw = str(value or "")
            selected_values = [
                i.strip()
                for i in raw.replace(",", "、").split("、")
                if i.strip()
            ]
        module_l1 = ""
        module_l2 = ""
        if fd.get("widget") == "module_cascade":
            if isinstance(value, str) and "/" in value:
                parts = [p.strip() for p in value.split("/", 1)]
                module_l1 = parts[0] if parts else ""
                module_l2 = parts[1] if len(parts) > 1 else ""
        stage_form_rows.append(
            {
                "key": fd["key"],
                "label": fd["label"],
                "widget": fd.get("widget", "text"),
                "required": _is_field_required(fd, all_values),
                "options": fd.get("options", []),
                "value": value,
                "selected_values": selected_values,
                "module_l1": module_l1,
                "module_l2": module_l2,
            }
        )
    snapshot_mode = request.GET.get("snapshot", "key")
    stage_snapshots = _stage_snapshots(ticket, key_only=(snapshot_mode != "all"))
    stage_timeline = _stage_timeline(ticket)
    advance_flow_payload = _advance_flow_payload(advance_options)
    return render(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "logs": logs,
            "stages": TicketStage.choices,
            "advance_options": advance_options,
            "advance_flow_payload": advance_flow_payload,
            "prev_stage": prev_stage,
            "prev_stage_label": prev_stage_label,
            "active_users": users,
            "stage_field_defs": stage_field_defs,
            "stage_form_rows": stage_form_rows,
            "module_tree": module_tree,
            "can_advance": bool(advance_options)
            and can_handle_stage(request.user, ticket.stage)
            and _can_operate_ticket(request.user, ticket),
            "can_transfer": can_handle_stage(request.user, ticket.stage)
            and ticket.stage != TicketStage.CLOSED
            and not stage_has_disposition_flow
            and _can_operate_ticket(request.user, ticket),
            "can_edit_fields": can_handle_stage(request.user, ticket.stage)
            and _can_operate_ticket(request.user, ticket),
            "can_rollback": can_handle_stage(request.user, ticket.stage)
            and ticket.stage != TicketStage.CLOSED
            and not stage_has_disposition_flow
            and _can_operate_ticket(request.user, ticket),
            "can_revoke": ticket.stage == TicketStage.HCS_SUBMIT
            and can_handle_stage(request.user, ticket.stage)
            and _can_operate_ticket(request.user, ticket),
            "stage_snapshots": stage_snapshots,
            "snapshot_mode": snapshot_mode,
            "stage_timeline": stage_timeline,
        },
    )


def _hcs_field_defs_for_create(submit_source="hcs"):
    """新建提单页不展示「处理方式」，流转在详情页与其它阶段一致（下拉 + 保存并确认流转）。"""
    return [
        fd
        for fd in get_field_defs_for_stage(
            TicketStage.HCS_SUBMIT, context={"submit_source": submit_source}
        )
        if fd["key"] != "disposition"
    ]


@login_required
def ticket_create(request):
    if not can_create_ticket(request.user):
        messages.error(request, "当前账号无提单权限（需具备 HCS提单 阶段处理能力）")
        return redirect("ticket_list")
    submit_source = _infer_submit_source_from_user(request.user)
    hcs_defs = _hcs_field_defs_for_create(submit_source)
    User = get_user_model()
    issue_review_users = [
        u
        for u in User.objects.filter(is_active=True).order_by("username")[:400]
        if can_handle_stage(u, TicketStage.ISSUE_REVIEW)
    ]
    if request.method == "GET":
        users = User.objects.filter(is_active=True).order_by("username")[:300]
        return render(
            request,
            "tickets/create.html",
            {
                "hcs_rows": _build_rows(hcs_defs, {}),
                "title_value": "",
                "description_value": "",
                "active_users": users,
                "issue_review_users": issue_review_users,
                "review_assignee_id": "",
            },
        )

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        is_self = request.POST.get("is_self_service") == "1"
        hcs_values = _extract_fields(hcs_defs, request.POST)
        missing_labels = _missing_required_labels(hcs_defs, hcs_values)
        if not title:
            users = get_user_model().objects.filter(is_active=True).order_by("username")[
                :300
            ]
            return render(
                request,
                "tickets/create.html",
                {
                    "error": "请填写标题",
                    "hcs_rows": _build_rows(hcs_defs, hcs_values),
                    "title_value": title,
                    "description_value": description,
                    "active_users": users,
                    "issue_review_users": issue_review_users,
                    "review_assignee_id": (request.POST.get("review_assignee_id") or ""),
                },
            )
        if missing_labels:
            User = get_user_model()
            users = User.objects.filter(is_active=True).order_by("username")[:300]
            issue_review_users = [
                u
                for u in User.objects.filter(is_active=True).order_by("username")[:300]
                if can_handle_stage(u, TicketStage.ISSUE_REVIEW)
            ]
            return render(
                request,
                "tickets/create.html",
                {
                    "error": "HCS提单必填缺失：" + "、".join(missing_labels),
                    "hcs_rows": _build_rows(hcs_defs, hcs_values),
                    "title_value": title,
                    "description_value": description,
                    "active_users": users,
                    "issue_review_users": issue_review_users,
                    "review_assignee_id": (request.POST.get("review_assignee_id") or ""),
                },
            )
        User = get_user_model()
        issue_review_users = [
            u
            for u in User.objects.filter(is_active=True).order_by("username")[:300]
            if can_handle_stage(u, TicketStage.ISSUE_REVIEW)
        ]
        reviewer = None
        if not is_self:
            review_raw = (request.POST.get("review_assignee_id") or "").strip()
            if not review_raw.isdigit():
                return render(
                    request,
                    "tickets/create.html",
                    {
                        "error": "请选择问题审核人",
                        "hcs_rows": _build_rows(hcs_defs, hcs_values),
                        "title_value": title,
                        "description_value": description,
                        "active_users": User.objects.filter(is_active=True).order_by(
                            "username"
                        )[:300],
                        "issue_review_users": issue_review_users,
                        "review_assignee_id": review_raw,
                    },
                )
            try:
                reviewer = User.objects.get(pk=int(review_raw), is_active=True)
            except User.DoesNotExist:
                return render(
                    request,
                    "tickets/create.html",
                    {
                        "error": "问题审核人无效",
                        "hcs_rows": _build_rows(hcs_defs, hcs_values),
                        "title_value": title,
                        "description_value": description,
                        "active_users": User.objects.filter(is_active=True).order_by(
                            "username"
                        )[:300],
                        "issue_review_users": issue_review_users,
                        "review_assignee_id": review_raw,
                    },
                )
            if not can_handle_stage(reviewer, TicketStage.ISSUE_REVIEW):
                return render(
                    request,
                    "tickets/create.html",
                    {
                        "error": "所选用户不具备问题审核阶段处理权限",
                        "hcs_rows": _build_rows(hcs_defs, hcs_values),
                        "title_value": title,
                        "description_value": description,
                        "active_users": User.objects.filter(is_active=True)
                        .order_by("username")[:300],
                        "issue_review_users": issue_review_users,
                        "review_assignee_id": review_raw,
                    },
                )
        assign_note = ""
        ops_assignee = None
        if is_self:
            ops_assignee, assign_note = pick_assignee(
                identities=_ticket_user_identities(request.user)
            )
            if not ops_assignee:
                return render(
                    request,
                    "tickets/create.html",
                    {
                        "error": "值班系统暂无可派运维人员：%s" % assign_note,
                        "hcs_rows": _build_rows(hcs_defs, hcs_values),
                        "title_value": title,
                        "description_value": description,
                        "active_users": User.objects.filter(is_active=True).order_by(
                            "username"
                        )[:300],
                        "issue_review_users": issue_review_users,
                        "review_assignee_id": "",
                    },
                )
        with transaction.atomic():
            ticket = Ticket.objects.create(
                title=title,
                description=description,
                reporter=request.user,
                is_self_service=is_self,
            )
            ticket.extra_data = {
                "stage_fields": {
                    TicketStage.HCS_SUBMIT: hcs_values,
                },
                "meta": {"submit_source": submit_source},
            }
            if is_self:
                ticket.stage = TicketStage.OPS_ANALYSIS
                ticket.assignee = ops_assignee
                _assignee_stage_map_write(
                    ticket, TicketStage.OPS_ANALYSIS, ops_assignee.id
                )
                ticket.save(
                    update_fields=["stage", "assignee", "extra_data", "updated_at"]
                )
                TicketTransitionLog.objects.create(
                    ticket=ticket,
                    from_stage=TicketStage.HCS_SUBMIT,
                    to_stage=TicketStage.OPS_ANALYSIS,
                    operator=request.user,
                    note="原阶段处理人：%s；目标阶段处理人：%s；运维自提单进入运维分析：%s"
                    % (_user_short(request.user), _user_short(ops_assignee), assign_note),
                )
            else:
                ticket.stage = TicketStage.ISSUE_REVIEW
                ticket.assignee = reviewer
                _assignee_stage_map_write(
                    ticket, TicketStage.ISSUE_REVIEW, reviewer.id
                )
                ticket.save(
                    update_fields=["stage", "assignee", "extra_data", "updated_at"]
                )
                TicketTransitionLog.objects.create(
                    ticket=ticket,
                    from_stage=TicketStage.HCS_SUBMIT,
                    to_stage=TicketStage.ISSUE_REVIEW,
                    operator=request.user,
                    note="原阶段处理人：%s；目标阶段处理人：%s"
                    % (_user_short(request.user), _user_short(reviewer)),
                )
        return redirect("ticket_detail", pk=ticket.pk)
    return render(
        request,
        "tickets/create.html",
        {
            "hcs_rows": _build_rows(hcs_defs, {}),
            "title_value": "",
            "description_value": "",
            "active_users": User.objects.filter(is_active=True).order_by("username")[
                :300
            ],
            "issue_review_users": issue_review_users,
            "review_assignee_id": "",
        },
    )


DISPOSITION_STAGE_MAP = {
    TicketStage.HCS_SUBMIT: {
        "提交至问题审核": TicketStage.ISSUE_REVIEW,
        "进入运维人员分析（运维自提单，值班系统分单）": TicketStage.OPS_ANALYSIS,
    },
    TicketStage.ISSUE_REVIEW: {
        "打回HCS提单": TicketStage.HCS_SUBMIT,
        "进入运维人员分析（值班系统分单）": TicketStage.OPS_ANALYSIS,
    },
    TicketStage.OPS_ANALYSIS: {
        "分配其他运维人员（同阶段）": TicketStage.OPS_ANALYSIS,
        "指定开发人员分析": TicketStage.DEV_ANALYSIS,
        "指定开发人员闭环": TicketStage.DEV_REVIEW,
        "进入运维人员闭环": TicketStage.OPS_CLOSURE,
    },
    TicketStage.DEV_ANALYSIS: {
        "分配其他开发人员（同阶段）": TicketStage.DEV_ANALYSIS,
        "进入开发人员闭环": TicketStage.DEV_REVIEW,
    },
    TicketStage.DEV_REVIEW: {
        "进入运维人员闭环": TicketStage.OPS_CLOSURE,
    },
    TicketStage.OPS_CLOSURE: {
        "进入问题审核关闭": TicketStage.AUDIT_CLOSE,
    },
    TicketStage.AUDIT_CLOSE: {
        "问题解决关闭": TicketStage.CLOSED,
        "返回运维人员闭环": TicketStage.OPS_CLOSURE,
    },
}


def _next_stage_of(current_stage):
    flow = [
        TicketStage.HCS_SUBMIT,
        TicketStage.ISSUE_REVIEW,
        TicketStage.OPS_ANALYSIS,
        TicketStage.DEV_ANALYSIS,
        TicketStage.DEV_REVIEW,
        TicketStage.OPS_CLOSURE,
        TicketStage.AUDIT_CLOSE,
        TicketStage.CLOSED,
    ]
    if current_stage not in flow:
        return None
    idx = flow.index(current_stage)
    if idx >= len(flow) - 1:
        return None
    return flow[idx + 1]


def _previous_stage_of(current_stage):
    flow = [
        TicketStage.HCS_SUBMIT,
        TicketStage.ISSUE_REVIEW,
        TicketStage.OPS_ANALYSIS,
        TicketStage.DEV_ANALYSIS,
        TicketStage.DEV_REVIEW,
        TicketStage.OPS_CLOSURE,
        TicketStage.AUDIT_CLOSE,
        TicketStage.CLOSED,
    ]
    if current_stage not in flow:
        return None
    idx = flow.index(current_stage)
    if idx <= 0:
        return None
    return flow[idx - 1]


def _resolve_next_stage(ticket, advance_choice=""):
    current_stage = ticket.stage
    if not advance_choice:
        return None
    return DISPOSITION_STAGE_MAP.get(current_stage, {}).get(advance_choice)


def _user_option_label(user):
    name = (user.get_full_name() or "").strip()
    return "%s（%s）" % (name or user.username, user.username)


def _user_short(user):
    if not user:
        return "未指定"
    return _user_option_label(user)


def _advance_options(ticket):
    defs = get_field_defs_for_stage(
        ticket.stage, context={"submit_source": _get_submit_source(ticket)}
    )
    disposition_options = []
    for fd in defs:
        if fd["key"] == "disposition":
            disposition_options = fd.get("options") or []
            break
    labels = dict(TicketStage.choices)
    pairs = []
    for disposition in disposition_options:
        to_stage = DISPOSITION_STAGE_MAP.get(ticket.stage, {}).get(disposition)
        if not to_stage:
            continue
        pairs.append((disposition, to_stage))
    unique_targets = list({t for _, t in pairs})
    all_users = list(
        get_user_model().objects.filter(is_active=True).order_by("username")[:500]
    )
    users_by_stage = {}
    for st in unique_targets:
        users_by_stage[st] = [
            u for u in all_users if can_handle_stage(u, st)
        ]
    out = []
    for disposition, to_stage in pairs:
        is_auto_assign = _should_duty_pick_for_ops(ticket.stage, to_stage)
        out.append(
            {
                "value": disposition,
                "label": "%s -> %s" % (disposition, labels.get(to_stage, to_stage)),
                "to_stage": to_stage,
                "is_close": to_stage == TicketStage.CLOSED,
                "is_auto_assign": is_auto_assign,
                "assignees": [
                    {"id": u.id, "label": _user_option_label(u)}
                    for u in ([] if is_auto_assign else users_by_stage.get(to_stage, []))
                ],
            }
        )
    return out


def _advance_flow_payload(advance_options):
    """供前端 json_script 联动「下一处理人」下拉。"""
    return [
        {
            "value": o["value"],
            "to_stage": o["to_stage"],
            "is_close": o.get("is_close", False),
            "is_auto_assign": o.get("is_auto_assign", False),
            "assignees": o.get("assignees") or [],
        }
        for o in advance_options
    ]


def _advance_ticket(ticket, operator, advance_choice="", next_assignee_id=None):
    if ticket.stage == TicketStage.CLOSED:
        return False, "问题单关闭状态不可再变更"
    defs = get_field_defs_for_stage(
        ticket.stage, context={"submit_source": _get_submit_source(ticket)}
    )
    allowed_dispositions = []
    for fd in defs:
        if fd["key"] == "disposition":
            allowed_dispositions = fd.get("options") or []
            break
    if advance_choice not in allowed_dispositions:
        return False, "处理方式非法或已废弃，请刷新页面后重试"
    next_stage = _resolve_next_stage(ticket, advance_choice=advance_choice)
    if not next_stage:
        return False, "请选择有效的处理方式"
    values = _get_stage_values(ticket, ticket.stage)
    if defs and any(fd["key"] == "disposition" for fd in defs):
        values = dict(values)
        values["disposition"] = advance_choice
    all_values = _all_stage_values(ticket)
    all_values["disposition"] = advance_choice
    missing_labels = _missing_required_labels(defs, values)
    if not missing_labels:
        # 二次过滤：联动可见且必填的字段
        missing_labels = _missing_required_labels(defs, values, all_values=all_values)
    if missing_labels:
        return False, "当前阶段必填未完成：" + "、".join(missing_labels)
    if defs and any(fd["key"] == "disposition" for fd in defs):
        _save_stage_field_value(ticket, ticket.stage, "disposition", advance_choice)
    from_stage = ticket.stage
    from_user = ticket.assignee
    next_user = None
    auto_assign_note = ""
    if _should_duty_pick_for_ops(from_stage, next_stage):
        next_user, auto_assign_note = pick_assignee(
            identities=_ticket_user_identities(ticket.reporter)
        )
        if not next_user:
            return False, "值班系统暂无可派运维人员：%s" % auto_assign_note
    elif next_stage != TicketStage.CLOSED:
        if not next_assignee_id:
            return False, "请选择下一处理人（须具备目标阶段处理权限）"
        try:
            next_user = get_user_model().objects.get(pk=next_assignee_id, is_active=True)
        except get_user_model().DoesNotExist:
            return False, "所选处理人无效或已停用"
        if not can_handle_stage(next_user, next_stage):
            return False, "所选用户不具备目标阶段处理权限，请重新选择"
    _inherit_common_fields(ticket, ticket.stage, next_stage)
    ticket.stage = next_stage
    if next_stage != TicketStage.CLOSED and next_user is not None:
        ticket.assignee = next_user
        _assignee_stage_map_write(ticket, next_stage, next_user.id)
    save_fields = ["stage", "extra_data", "updated_at", "assignee"]
    if from_stage == TicketStage.HCS_SUBMIT:
        ticket.is_self_service = next_stage == TicketStage.OPS_ANALYSIS
        save_fields.append("is_self_service")
    ticket.save(update_fields=save_fields)
    to_user = ticket.assignee if next_stage != TicketStage.CLOSED else None
    note = "原阶段处理人：%s；目标阶段处理人：%s；处理方式：%s" % (
        _user_short(from_user),
        _user_short(to_user) if next_stage != TicketStage.CLOSED else "无（问题单关闭）",
        advance_choice,
    )
    if _should_duty_pick_for_ops(from_stage, next_stage):
        note += "；值班分单：%s（%s）" % (_user_short(next_user), auto_assign_note)
    TicketTransitionLog.objects.create(
        ticket=ticket,
        from_stage=from_stage,
        to_stage=next_stage,
        operator=operator,
        note=note,
    )
    return True, "工单已推进到下一阶段"


def _rollback_ticket(ticket, operator, reason=""):
    if ticket.stage == TicketStage.CLOSED:
        return False, "问题单关闭状态不可再变更"
    prev_stage = _previous_stage_of(ticket.stage)
    if not prev_stage:
        return False, "已是首阶段，无法回退"
    stage_map = _assignee_stage_map_get(ticket)
    prev_assignee_id = stage_map.get(prev_stage)
    prev_assignee = None
    if prev_assignee_id:
        prev_assignee = get_user_model().objects.filter(
            pk=prev_assignee_id, is_active=True
        ).first()
    if prev_assignee is not None:
        if not can_handle_stage(prev_assignee, prev_stage):
            return False, "上一阶段默认处理人已无该阶段权限，请先转派后再回退"
    elif ticket.assignee and not can_handle_stage(ticket.assignee, prev_stage):
        return False, "当前处理人无上一阶段处理权限，请先转派"
    from_stage = ticket.stage
    from_user = ticket.assignee
    ticket.stage = prev_stage
    if prev_assignee is not None:
        ticket.assignee = prev_assignee
    ticket.save(update_fields=["stage", "assignee", "updated_at"])
    to_user = ticket.assignee
    TicketTransitionLog.objects.create(
        ticket=ticket,
        from_stage=from_stage,
        to_stage=prev_stage,
        operator=operator,
        note="原阶段处理人：%s；目标阶段处理人：%s；回退上一阶段%s%s"
        % (
            _user_short(from_user),
            _user_short(to_user),
            "，原因：" if reason else "",
            reason,
        ),
    )
    return True, "工单已回退到上一阶段"


def _revoke_ticket(ticket, operator):
    if ticket.stage != TicketStage.HCS_SUBMIT:
        return False, "仅HCS提单阶段支持撤销"
    ticket_no = ticket.number
    ticket.delete()
    return True, "运维单 #%s 已撤销" % ticket_no


def _transfer_ticket(ticket, operator, assignee_id, assignee_query=""):
    if ticket.stage == TicketStage.CLOSED:
        return False, "问题单关闭状态不可再转派"
    if not assignee_id:
        return False, "请选择候选中的目标处理人（需命中搜索下拉）"
    user = get_object_or_404(get_user_model(), pk=assignee_id, is_active=True)
    if not can_handle_stage(user, ticket.stage):
        return False, "目标用户无当前阶段处理权限"
    old_user = ticket.assignee
    ticket.assignee = user
    _assignee_stage_map_write(ticket, ticket.stage, user.id)
    ticket.save(update_fields=["assignee", "updated_at"])
    TicketTransitionLog.objects.create(
        ticket=ticket,
        from_stage=ticket.stage,
        to_stage=ticket.stage,
        operator=operator,
        note="当前阶段处理人变更：%s -> %s" % (_user_short(old_user), _user_short(user)),
    )
    return True, "处理人已更新"


def _get_stage_values(ticket, stage):
    all_stage_data = (ticket.extra_data or {}).get("stage_fields", {})
    values = all_stage_data.get(stage, {})
    return values if isinstance(values, dict) else {}


def _save_stage_field_value(ticket, stage, key, value):
    extra = ticket.extra_data or {}
    stage_fields = extra.get("stage_fields", {})
    current = stage_fields.get(stage, {})
    if not isinstance(current, dict):
        current = {}
    current = dict(current)
    current[key] = value
    stage_fields[stage] = current
    extra["stage_fields"] = stage_fields
    ticket.extra_data = extra


def _update_stage_fields(ticket, stage, post, submit_source="hcs"):
    defs = get_field_defs_for_stage(stage, context={"submit_source": submit_source})
    if not defs:
        return
    extra = ticket.extra_data or {}
    stage_fields = extra.get("stage_fields", {})
    current = stage_fields.get(stage, {})
    if not isinstance(current, dict):
        current = {}
    all_values = _all_stage_values(ticket)
    all_values.update(current)
    changed_labels = []
    for fd in defs:
        if fd["key"] == "disposition":
            # disposition 由流转提交控制，避免“仅保存字段”时被空值覆盖
            continue
        if not _is_field_visible(fd, all_values):
            continue
        key = fd["key"]
        widget = fd.get("widget", "text")
        if widget == "user_multi_select":
            vals = [i.strip() for i in post.getlist(key) if i.strip()]
            new_val = "、".join(vals)
        elif widget == "module_cascade":
            new_val = (post.get(key) or "").strip()
            if not new_val:
                l1 = (post.get("%s__l1" % key) or "").strip()
                l2 = (post.get("%s__l2" % key) or "").strip()
                if l1 and l2:
                    new_val = "%s/%s" % (l1, l2)
        else:
            new_val = (post.get(key) or "").strip()
        old_val = (current.get(key) or "").strip() if isinstance(current.get(key), str) else current.get(key)
        current[key] = new_val
        if str(old_val or "") != str(new_val or ""):
            changed_labels.append(fd.get("label") or key)
        all_values[key] = current[key]
    stage_fields[stage] = current
    extra["stage_fields"] = stage_fields
    ticket.extra_data = extra
    ticket.save(update_fields=["extra_data", "updated_at"])
    return changed_labels


def _extract_fields(defs, post):
    values = {}
    for fd in defs:
        key = fd["key"]
        values[key] = (post.get(key) or "").strip()
    return values


def _missing_required_labels(defs, values, all_values=None):
    missing = []
    all_values = all_values or values
    for fd in defs:
        if not _is_field_visible(fd, all_values):
            continue
        if not _is_field_required(fd, all_values):
            continue
        key = fd["key"]
        if not (values.get(key) or "").strip():
            missing.append(fd["label"])
    return missing


def _build_rows(defs, values):
    rows = []
    for fd in defs:
        rows.append(
            {
                "key": fd["key"],
                "label": fd["label"],
                "widget": fd.get("widget", "text"),
                "required": bool(fd.get("required")),
                "options": fd.get("options", []),
                "value": values.get(fd["key"], ""),
            }
        )
    return rows


def _build_ticket_list_row(ticket):
    def display_name(user):
        if not user:
            return "-"
        name = (user.get_full_name() or "").strip()
        return name or user.username

    def pick(*keys):
        for stage_map in (ticket.extra_data or {}).get("stage_fields", {}).values():
            if not isinstance(stage_map, dict):
                continue
            for k in keys:
                v = (stage_map.get(k) or "").strip() if isinstance(stage_map.get(k), str) else stage_map.get(k)
                if v:
                    return v
        return ""

    start_date = pick("start_date")
    severity = pick("severity")
    site = pick("site")
    instance = pick("instance_short_name")
    business_env = pick("business_env")
    desc = pick("issue_description") or ticket.description
    severity_for_sla = severity if severity and severity != "-" else pick("severity")
    sla = _compute_sla_metric(ticket, severity_for_sla)
    stayed = timezone.now() - ticket.updated_at
    stayed_hours = int(stayed.total_seconds() // 3600)
    return {
        "obj": ticket,
        "number": ticket.number,
        "stage_display": ticket.get_stage_display(),
        "start_date": start_date or "-",
        "severity": severity or "-",
        "site": site or "-",
        "instance_short_name": instance or "-",
        "business_env": business_env or "-",
        "assignee": display_name(ticket.assignee),
        "issue_description": desc or "-",
        "stayed": "%s小时" % stayed_hours,
        "sla": sla or "-",
    }


def _compute_sla_metric(ticket, severity):
    # 可按你们后续规则调整阈值
    hours_map = {"一般": 72, "严重": 24, "致命": 8, "事故": 4}
    target = hours_map.get(severity)
    if not target:
        return "-"
    used = int((timezone.now() - ticket.created_at).total_seconds() // 3600)
    remain = target - used
    if remain >= 0:
        return "剩余%s小时/%s小时" % (remain, target)
    return "超时%s小时/%s小时" % (abs(remain), target)


def _all_stage_values(ticket):
    merged = {}
    stage_fields = (ticket.extra_data or {}).get("stage_fields", {})
    for stage_map in stage_fields.values():
        if isinstance(stage_map, dict):
            merged.update(stage_map)
    return merged


def _inherit_common_fields(ticket, from_stage, to_stage):
    extra = ticket.extra_data or {}
    stage_fields = extra.get("stage_fields", {})
    src = stage_fields.get(from_stage, {})
    dst = stage_fields.get(to_stage, {})
    if not isinstance(src, dict):
        return
    if not isinstance(dst, dict):
        dst = {}
    for key, val in src.items():
        if key not in dst or not (dst.get(key) or "").strip():
            dst[key] = val
    stage_fields[to_stage] = dst
    extra["stage_fields"] = stage_fields
    ticket.extra_data = extra


def _stage_snapshots(ticket, key_only=True):
    stage_fields = (ticket.extra_data or {}).get("stage_fields", {})
    snapshots = []
    for stage, label in TicketStage.choices:
        values = stage_fields.get(stage, {})
        if not isinstance(values, dict) or not values:
            continue
        defs = get_field_defs_for_stage(stage, context={"submit_source": _get_submit_source(ticket)})
        label_map = {fd.get("key"): fd.get("label") for fd in defs}
        rows = []
        for k, v in values.items():
            if v in (None, ""):
                continue
            if k.endswith("_id"):
                continue
            if key_only and k not in {
                "start_date",
                "severity",
                "site",
                "issue_description",
                "disposition",
                "issue_type_prejudge",
                "owned_module",
                "is_quality_issue",
                "root_cause",
                "business_impact",
                "need_alert",
                "external_reply",
            }:
                continue
            rows.append({"label": label_map.get(k, k), "value": v})
        if rows:
            snapshots.append({"stage_label": label, "rows": rows})
    return snapshots


def _get_submit_source(ticket):
    return ((ticket.extra_data or {}).get("meta", {}) or {}).get("submit_source", "hcs")


def _infer_submit_source_from_user(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return "hcs"
    ids = [s.lower() for s in profile.identity_list()]
    if "bu" in ids:
        return "bu"
    return "hcs"


def _ticket_user_identities(user):
    profile = getattr(user, "profile", None)
    if not profile:
        return []
    return [s.strip().lower() for s in profile.identity_list() if s.strip()]


def _is_field_visible(fd, all_values):
    cond = fd.get("show_when") or {}
    if not cond:
        return True
    return _match_conditions(cond, all_values)


def _is_field_required(fd, all_values):
    if fd.get("required"):
        return True
    cond = fd.get("required_when") or {}
    if not cond:
        return False
    return _match_conditions(cond, all_values)


def _match_conditions(conds, values):
    for key, expects in conds.items():
        val = (values.get(key) or "")
        ok = False
        for exp in expects:
            if isinstance(exp, str) and exp.startswith("contains:"):
                needle = exp.split(":", 1)[1]
                if needle in str(val):
                    ok = True
                    break
            elif str(val) == str(exp):
                ok = True
                break
        if not ok:
            return False
    return True


def _can_operate_ticket(user, ticket):
    return bool(ticket.assignee_id and ticket.assignee_id == user.id)


def _stage_timeline(ticket):
    stage_index = {v: i for i, (v, _) in enumerate(TicketStage.choices)}
    current_idx = stage_index.get(ticket.stage, 0)
    done = set(
        ticket.transitions.values_list("to_stage", flat=True)
    )
    rows = []
    for idx, (stage, label) in enumerate(TicketStage.choices):
        if stage == ticket.stage:
            status = "current"
        elif stage in done or idx < current_idx:
            status = "done"
        else:
            status = "todo"
        rows.append({"stage": stage, "label": label, "status": status})
    return rows
