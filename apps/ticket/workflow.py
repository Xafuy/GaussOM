from collections import namedtuple

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.dispatch.assign import assign_on_stage_enter
from apps.ticket.constants import (
    STAGE_DEV_ANALYSIS,
    STAGE_DEV_AUDIT,
    STAGE_OPS_ANALYSIS,
    STAGE_OPS_CLOSE,
    STAGE_REVIEW,
    STAGE_REVIEW_CLOSE,
    STAGE_SUBMIT,
)
from apps.ticket.models import Ticket, TicketAssigneeHistory, TicketOperationLog, TicketTransition

User = get_user_model()

TransitionSpec = namedtuple(
    "TransitionSpec",
    ["action_code", "label", "to_stage", "needs_assignee_pick", "closes_ticket"],
)


SELF_ENTRY_STAGE = STAGE_OPS_ANALYSIS


def allowed_actions(ticket):
    if ticket.status != Ticket.TicketStatus.PROCESSING:
        return []
    s = ticket.current_stage_code
    specs = []
    if s == STAGE_SUBMIT:
        specs.append(TransitionSpec("submit_review", "送审（进入问题审核）", STAGE_REVIEW, False, False))
    elif s == STAGE_REVIEW:
        specs.append(TransitionSpec("pass_to_ops", "通过 → 运维分析", STAGE_OPS_ANALYSIS, False, False))
        specs.append(TransitionSpec("reject_to_submit", "退回提单", STAGE_SUBMIT, False, False))
        specs.append(
            TransitionSpec(
                "close_ticket",
                "审核关闭（提前关单）",
                STAGE_REVIEW_CLOSE,
                False,
                True,
            )
        )
    elif s == STAGE_OPS_ANALYSIS:
        specs.append(TransitionSpec("to_dev", "转开发人员分析", STAGE_DEV_ANALYSIS, False, False))
        specs.append(TransitionSpec("ops_direct_close", "运维直接闭环", STAGE_OPS_CLOSE, False, False))
        specs.append(
            TransitionSpec(
                "transfer_ops",
                "内部转单（运维分析）",
                STAGE_OPS_ANALYSIS,
                True,
                False,
            )
        )
    elif s == STAGE_DEV_ANALYSIS:
        specs.append(TransitionSpec("to_dev_audit", "提交开发审核", STAGE_DEV_AUDIT, False, False))
        specs.append(
            TransitionSpec(
                "transfer_dev",
                "内部转单（开发分析）",
                STAGE_DEV_ANALYSIS,
                True,
                False,
            )
        )
    elif s == STAGE_DEV_AUDIT:
        specs.append(TransitionSpec("audit_pass", "审核通过 → 运维闭环", STAGE_OPS_CLOSE, False, False))
        specs.append(TransitionSpec("audit_reject", "退回开发分析", STAGE_DEV_ANALYSIS, False, False))
    elif s == STAGE_OPS_CLOSE:
        specs.append(
            TransitionSpec("to_review_close", "提交终审关闭", STAGE_REVIEW_CLOSE, False, False)
        )
    elif s == STAGE_REVIEW_CLOSE:
        specs.append(
            TransitionSpec(
                "finalize_close",
                "确认关单",
                STAGE_REVIEW_CLOSE,
                False,
                True,
            )
        )
    return specs


def _log_op(ticket, user, op, before, after):
    TicketOperationLog.objects.create(
        ticket=ticket,
        operation_type=op,
        operator_user=user,
        before_json=before,
        after_json=after,
    )


@transaction.atomic
def apply_transition(
    ticket: Ticket,
    operator: User,
    action_code: str,
    *,
    comment: str = "",
    target_user_id=None,
):
    specs = {s.action_code: s for s in allowed_actions(ticket)}
    spec = specs.get(action_code)
    if not spec:
        return False, "当前阶段不允许该操作。"

    target_user = None
    if spec.needs_assignee_pick:
        if not target_user_id:
            return False, "请选择接手人。"
        target_user = User.objects.filter(pk=target_user_id).first()
        if not target_user:
            return False, "接手人不存在。"

    from_stage = ticket.current_stage_code
    from_assignee = ticket.current_assignee
    to_stage = spec.to_stage

    before = {
        "stage": ticket.current_stage_code,
        "assignee_id": ticket.current_assignee_id,
        "status": ticket.status,
    }

    ticket.current_stage_code = to_stage

    if spec.needs_assignee_pick and target_user:
        ticket.current_assignee = target_user
        TicketAssigneeHistory.objects.create(
            ticket=ticket,
            stage_code=to_stage,
            assignee_user=target_user,
            assign_type=TicketAssigneeHistory.AssignType.MANUAL,
        )
    elif action_code == "close_ticket":
        ticket.status = Ticket.TicketStatus.CLOSED
        ticket.closed_at = timezone.now()
    elif action_code == "finalize_close":
        ticket.status = Ticket.TicketStatus.CLOSED
        ticket.closed_at = timezone.now()
    elif not spec.closes_ticket:
        assign_on_stage_enter(ticket, to_stage, operator)

    ticket.save(
        update_fields=[
            "current_stage_code",
            "current_assignee",
            "status",
            "closed_at",
            "updated_at",
        ]
    )

    TicketTransition.objects.create(
        ticket=ticket,
        from_stage_code=from_stage,
        to_stage_code=to_stage,
        action_code=action_code,
        operator_user=operator,
        from_assignee=from_assignee,
        to_assignee=ticket.current_assignee,
        comment=comment or "",
    )

    after = {
        "stage": ticket.current_stage_code,
        "assignee_id": ticket.current_assignee_id,
        "status": ticket.status,
    }
    _log_op(ticket, operator, f"transition:{action_code}", before, after)
    return True, "操作成功。"


def user_can_operate_ticket(ticket, user):
    if not user.is_authenticated:
        return False
    if user.is_staff or getattr(user, "is_admin", False):
        return True
    if ticket.creator_user_id == user.id:
        return True
    if ticket.current_assignee_id == user.id:
        return True
    return False


def generate_ticket_no():
    from datetime import datetime

    prefix = datetime.now().strftime("OM-%Y%m%d")
    last = (
        Ticket.objects.filter(ticket_no__startswith=prefix)
        .order_by("-ticket_no")
        .values_list("ticket_no", flat=True)
        .first()
    )
    seq = 1
    if last:
        part = last.rsplit("-", 1)[-1]
        if part.isdigit():
            seq = int(part) + 1
    return f"{prefix}-{seq:04d}"


def create_ticket_initial(
    *,
    creator: User,
    source_type: str,
    issue_type: str,
) -> Ticket:
    stage = STAGE_SUBMIT
    assignee = None
    if source_type == Ticket.SourceType.SELF:
        stage = SELF_ENTRY_STAGE
        assignee = creator

    ticket = Ticket.objects.create(
        ticket_no=generate_ticket_no(),
        source_type=source_type,
        current_stage_code=stage,
        current_assignee=assignee,
        creator_user=creator,
        issue_type=issue_type or "",
        status=Ticket.TicketStatus.PROCESSING,
    )
    if assignee:
        TicketAssigneeHistory.objects.create(
            ticket=ticket,
            stage_code=stage,
            assignee_user=assignee,
            assign_type=TicketAssigneeHistory.AssignType.AUTO,
        )
    TicketTransition.objects.create(
        ticket=ticket,
        from_stage_code="",
        to_stage_code=stage,
        action_code="create",
        operator_user=creator,
        from_assignee=None,
        to_assignee=assignee,
        comment="创建工单",
    )
    TicketOperationLog.objects.create(
        ticket=ticket,
        operation_type="create",
        operator_user=creator,
        before_json=None,
        after_json={
            "stage": stage,
            "assignee_id": assignee.pk if assignee else None,
        },
    )
    return ticket
