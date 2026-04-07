"""分单：按值班表轮询 + 兜底（与设计模块04一致，初版可配置）。"""

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.dispatch.models import DispatchCursor, DispatchDecisionLog
from apps.duty.models import DutySchedule, DutyScheduleMember
from apps.ticket.constants import (
    STAGE_DEV_ANALYSIS,
    STAGE_DEV_AUDIT,
    STAGE_OPS_ANALYSIS,
    STAGE_OPS_CLOSE,
    STAGE_REVIEW,
    STAGE_REVIEW_CLOSE,
    STAGE_SUBMIT,
)
from apps.ticket.models import Ticket, TicketAssigneeHistory

User = get_user_model()


def _active_members_qs(schedule: DutySchedule):
    return (
        DutyScheduleMember.objects.filter(schedule=schedule, status="active")
        .select_related("user")
        .order_by("order_no", "id")
    )


@transaction.atomic
def _round_robin_pick(
    schedule: DutySchedule, biz_scene: str, ticket, policy=None, rule=None
):
    members = list(_active_members_qs(schedule))
    if not members:
        return None
    cursor, _ = DispatchCursor.objects.select_for_update().get_or_create(
        schedule=schedule,
        biz_scene=biz_scene,
        defaults={"current_member": None},
    )
    current_id = cursor.current_member_id
    idx = 0
    if current_id:
        ids = [m.id for m in members]
        if current_id in ids:
            idx = (ids.index(current_id) + 1) % len(members)
    chosen = members[idx]
    cursor.current_member = chosen
    cursor.save(update_fields=["current_member", "updated_at"])

    DispatchDecisionLog.objects.create(
        ticket=ticket,
        policy=policy,
        hit_rule=rule,
        decision_path_json={
            "schedule_id": schedule.id,
            "schedule_code": schedule.schedule_code,
            "biz_scene": biz_scene,
            "member_id": chosen.id,
        },
        final_assignee=chosen.user,
        fallback_reason="",
    )
    return chosen.user


def _pick_schedule_for_issue(issue_type: str):
    if issue_type == "control":
        s = (
            DutySchedule.objects.filter(
                schedule_type=DutySchedule.ScheduleType.CONTROL, status="active"
            )
            .order_by("id")
            .first()
        )
        if s:
            return s
    return (
        DutySchedule.objects.filter(
            schedule_type=DutySchedule.ScheduleType.KERNEL, status="active"
        )
        .order_by("id")
        .first()
    )


def _dev_audit_assignee(ticket: Ticket):
    from apps.form.models import TicketFieldValue
    from apps.system.models import SysReviewerWhitelist

    module_code = (
        TicketFieldValue.objects.filter(
            ticket=ticket, field_code="problem_belong_module"
        )
        .values_list("field_value_text", flat=True)
        .first()
        or ""
    ).strip()

    qs = SysReviewerWhitelist.objects.filter(
        review_type=SysReviewerWhitelist.ReviewType.DEV_AUDIT,
        status="active",
    )
    if module_code:
        row = qs.filter(module_code=module_code).first()
        if row:
            return row.reviewer_user
    row = qs.first()
    if row:
        return row.reviewer_user
    return User.objects.filter(is_staff=True, is_active=True).order_by("id").first()


def assign_on_stage_enter(ticket: Ticket, to_stage: str, operator: User) -> None:
    """进入某阶段时的默认分单（无值班成员则兜底为提单人）。"""
    assignee = None
    schedule = _pick_schedule_for_issue(ticket.issue_type or "")

    if to_stage == STAGE_SUBMIT:
        assignee = ticket.creator_user
        DispatchDecisionLog.objects.create(
            ticket=ticket,
            policy=None,
            hit_rule=None,
            decision_path_json={"reason": "return_to_submit"},
            final_assignee=assignee,
            fallback_reason="退回提单，由提单人处理",
        )
        ticket.current_assignee = assignee
        ticket.save(update_fields=["current_assignee", "updated_at"])
        TicketAssigneeHistory.objects.create(
            ticket=ticket,
            stage_code=to_stage,
            assignee_user=assignee,
            assign_type=TicketAssigneeHistory.AssignType.MANUAL,
        )
        return

    if to_stage == STAGE_REVIEW and schedule:
        assignee = _round_robin_pick(
            schedule, DispatchCursor.BizScene.DAY, ticket
        )
    elif to_stage in (STAGE_OPS_ANALYSIS, STAGE_DEV_ANALYSIS) and schedule:
        assignee = _round_robin_pick(
            schedule, DispatchCursor.BizScene.KERNEL, ticket
        )
    elif to_stage == STAGE_OPS_CLOSE and schedule:
        assignee = _round_robin_pick(
            schedule, DispatchCursor.BizScene.KERNEL, ticket
        )
    elif to_stage == STAGE_DEV_AUDIT:
        assignee = _dev_audit_assignee(ticket)
    elif to_stage == STAGE_REVIEW_CLOSE:
        assignee = (
            User.objects.filter(is_staff=True, is_active=True).order_by("id").first()
            or ticket.creator_user
        )
        DispatchDecisionLog.objects.create(
            ticket=ticket,
            policy=None,
            hit_rule=None,
            decision_path_json={"reason": "review_close_assign"},
            final_assignee=assignee,
            fallback_reason="终审默认分给值班管理员或提单人",
        )
        ticket.current_assignee = assignee
        ticket.save(update_fields=["current_assignee", "updated_at"])
        TicketAssigneeHistory.objects.create(
            ticket=ticket,
            stage_code=to_stage,
            assignee_user=assignee,
            assign_type=TicketAssigneeHistory.AssignType.AUTO,
        )
        return

    if assignee is None:
        assignee = ticket.creator_user
        DispatchDecisionLog.objects.create(
            ticket=ticket,
            policy=None,
            hit_rule=None,
            decision_path_json={"reason": "no_schedule_or_member"},
            final_assignee=assignee,
            fallback_reason="无可用值班成员，分给提单人",
        )

    ticket.current_assignee = assignee
    ticket.save(update_fields=["current_assignee", "updated_at"])
    TicketAssigneeHistory.objects.create(
        ticket=ticket,
        stage_code=to_stage,
        assignee_user=assignee,
        assign_type=TicketAssigneeHistory.AssignType.AUTO,
    )
