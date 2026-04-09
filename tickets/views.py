from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from rbac.services import can_create_ticket, can_handle_stage, has_permission
from scheduling.services import pick_assignee

from .models import Ticket, TicketStage, TicketTransitionLog
from .stage_fields import get_field_defs_for_stage


@login_required
def ticket_list(request):
    view_mode = request.GET.get("view", "mine")
    stage_filter = request.GET.get("stage", "")
    keyword = (request.GET.get("q") or "").strip()

    qs = Ticket.objects.select_related("reporter", "assignee").all()
    if view_mode == "mine":
        # 默认：需要我处理且尚未关闭
        qs = qs.filter(assignee=request.user).exclude(stage=TicketStage.AUDIT_CLOSE)
    elif view_mode == "created":
        qs = qs.filter(reporter=request.user)
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
        if action == "advance":
            if has_permission(request.user, "ticket:advance") and can_handle_stage(
                request.user, ticket.stage
            ):
                ok, msg = _advance_ticket(ticket=ticket, operator=request.user)
                if ok:
                    messages.success(request, msg)
                else:
                    messages.error(request, msg)
            else:
                messages.error(request, "无权限：ticket:advance")
        elif action == "transfer":
            assignee_id = request.POST.get("assignee_id")
            assignee_query = (request.POST.get("assignee_query") or "").strip()
            if has_permission(request.user, "ticket:transfer") and can_handle_stage(
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
                messages.error(request, "无权限：ticket:transfer 或当前阶段处理权限不足")
        elif action == "update_fields":
            if has_permission(request.user, "ticket:edit_fields") and can_handle_stage(
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
                        note="更新字段: %s" % "、".join(changed_labels[:12]),
                    )
                messages.success(request, "阶段字段已保存")
            else:
                messages.error(request, "无权限：ticket:edit_fields 或当前阶段处理权限不足")
        return redirect("ticket_detail", pk=ticket.pk)

    logs = ticket.transitions.select_related("operator")[:50]
    users = [
        u
        for u in get_user_model().objects.filter(is_active=True).order_by("username")[:300]
        if can_handle_stage(u, ticket.stage)
    ]
    next_stage = _next_stage_of(ticket.stage)
    next_stage_label = dict(TicketStage.choices).get(next_stage, "")
    stage_field_defs = get_field_defs_for_stage(
        ticket.stage, context={"submit_source": submit_source}
    )
    stage_field_values = _get_stage_values(ticket, ticket.stage)
    all_values = _all_stage_values(ticket)
    stage_form_rows = []
    for fd in stage_field_defs:
        if not _is_field_visible(fd, all_values):
            continue
        stage_form_rows.append(
            {
                "key": fd["key"],
                "label": fd["label"],
                "widget": fd.get("widget", "text"),
                "required": _is_field_required(fd, all_values),
                "options": fd.get("options", []),
                "value": stage_field_values.get(fd["key"], "")
                or all_values.get(fd["key"], ""),
            }
        )
    snapshot_mode = request.GET.get("snapshot", "key")
    stage_snapshots = _stage_snapshots(ticket, key_only=(snapshot_mode != "all"))
    return render(
        request,
        "tickets/detail.html",
        {
            "ticket": ticket,
            "logs": logs,
            "stages": TicketStage.choices,
            "next_stage": next_stage,
            "next_stage_label": next_stage_label,
            "active_users": users,
            "stage_field_defs": stage_field_defs,
            "stage_form_rows": stage_form_rows,
            "can_advance": has_permission(request.user, "ticket:advance")
            and can_handle_stage(request.user, ticket.stage),
            "can_transfer": has_permission(request.user, "ticket:transfer")
            and can_handle_stage(request.user, ticket.stage),
            "can_edit_fields": has_permission(request.user, "ticket:edit_fields")
            and can_handle_stage(request.user, ticket.stage),
            "stage_snapshots": stage_snapshots,
            "snapshot_mode": snapshot_mode,
        },
    )


@login_required
def ticket_create(request):
    if not can_create_ticket(request.user):
        messages.error(request, "当前账号身份无提单权限（仅 BU/管控/运维可提单）")
        return redirect("ticket_list")
    hcs_defs = get_field_defs_for_stage(TicketStage.HCS_SUBMIT)
    if request.method == "GET":
        users = get_user_model().objects.filter(is_active=True).order_by("username")[:300]
        return render(
            request,
            "tickets/create.html",
            {
                "hcs_rows": _build_rows(hcs_defs, {}),
                "title_value": "",
                "description_value": "",
                "active_users": users,
            },
        )

    if request.method == "POST":
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        is_self = request.POST.get("is_self_service") == "1"
        submit_source = _infer_submit_source_from_user(request.user)
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
                },
            )
        if missing_labels:
            users = get_user_model().objects.filter(is_active=True).order_by("username")[
                :300
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
                ticket.assignee = request.user
                ticket.save(
                    update_fields=["stage", "assignee", "extra_data", "updated_at"]
                )
                TicketTransitionLog.objects.create(
                    ticket=ticket,
                    from_stage=TicketStage.HCS_SUBMIT,
                    to_stage=TicketStage.OPS_ANALYSIS,
                    operator=request.user,
                    note="运维自提单，跳过前置分流",
                )
            else:
                assignee, assign_note = pick_assignee(
                    identities=_ticket_user_identities(request.user)
                )
                ticket.stage = TicketStage.ISSUE_REVIEW
                ticket.assignee = assignee
                ticket.save(
                    update_fields=["stage", "assignee", "extra_data", "updated_at"]
                )
                TicketTransitionLog.objects.create(
                    ticket=ticket,
                    from_stage=TicketStage.HCS_SUBMIT,
                    to_stage=TicketStage.ISSUE_REVIEW,
                    operator=request.user,
                    note=assign_note,
                )
        return redirect("ticket_detail", pk=ticket.pk)
    return render(
        request,
        "tickets/create.html",
        {
            "hcs_rows": _build_rows(hcs_defs, {}),
            "title_value": "",
            "description_value": "",
            "active_users": get_user_model()
            .objects.filter(is_active=True)
            .order_by("username")[:300],
        },
    )


def _next_stage_of(current_stage):
    flow = [
        TicketStage.HCS_SUBMIT,
        TicketStage.ISSUE_REVIEW,
        TicketStage.OPS_ANALYSIS,
        TicketStage.DEV_ANALYSIS,
        TicketStage.DEV_REVIEW,
        TicketStage.OPS_CLOSURE,
        TicketStage.AUDIT_CLOSE,
    ]
    if current_stage not in flow:
        return None
    idx = flow.index(current_stage)
    if idx >= len(flow) - 1:
        return None
    return flow[idx + 1]


def _advance_ticket(ticket, operator):
    next_stage = _next_stage_of(ticket.stage)
    if not next_stage:
        return False, "已是最终阶段，无法继续推进"
    defs = get_field_defs_for_stage(
        ticket.stage, context={"submit_source": _get_submit_source(ticket)}
    )
    values = _get_stage_values(ticket, ticket.stage)
    all_values = _all_stage_values(ticket)
    missing_labels = _missing_required_labels(defs, values)
    if not missing_labels:
        # 二次过滤：联动可见且必填的字段
        missing_labels = _missing_required_labels(defs, values, all_values=all_values)
    if missing_labels:
        return False, "当前阶段必填未完成：" + "、".join(missing_labels)
    from_stage = ticket.stage
    if ticket.assignee and not can_handle_stage(ticket.assignee, next_stage):
        return False, "当前处理人无下一阶段处理权限，请先转派到有权限人员"
    _inherit_common_fields(ticket, ticket.stage, next_stage)
    ticket.stage = next_stage
    ticket.save(update_fields=["stage", "extra_data", "updated_at"])
    TicketTransitionLog.objects.create(
        ticket=ticket,
        from_stage=from_stage,
        to_stage=next_stage,
        operator=operator,
        note="手工推进阶段",
    )
    return True, "工单已推进到下一阶段"


def _transfer_ticket(ticket, operator, assignee_id, assignee_query=""):
    if not assignee_id:
        return False, "请选择候选中的目标处理人（需命中搜索下拉）"
    user = get_object_or_404(get_user_model(), pk=assignee_id, is_active=True)
    if not can_handle_stage(user, ticket.stage):
        return False, "目标用户无当前阶段处理权限"
    ticket.assignee = user
    ticket.save(update_fields=["assignee", "updated_at"])
    TicketTransitionLog.objects.create(
        ticket=ticket,
        from_stage=ticket.stage,
        to_stage=ticket.stage,
        operator=operator,
        note="转派处理人 -> %s" % user.username,
    )
    return True, "处理人已更新"


def _get_stage_values(ticket, stage):
    all_stage_data = (ticket.extra_data or {}).get("stage_fields", {})
    values = all_stage_data.get(stage, {})
    return values if isinstance(values, dict) else {}


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
        if not _is_field_visible(fd, all_values):
            continue
        key = fd["key"]
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
