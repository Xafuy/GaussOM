"""
写入便于联调的演示数据：用户、值班成员、审核白名单、固定单号工单与部分字段值。
可重复执行：按 ticket_no / username 幂等；可用 --purge 先删演示工单再重建。
"""

from django.core.management import call_command
from django.core.management.base import BaseCommand

from apps.duty.models import DutySchedule, DutyScheduleMember
from apps.form.models import TicketFieldValue
from apps.system.models import SysOrgGroup, SysReviewerWhitelist, SysUser
from apps.ticket.constants import (
    STAGE_DEV_ANALYSIS,
    STAGE_OPS_ANALYSIS,
    STAGE_REVIEW,
    STAGE_REVIEW_CLOSE,
    STAGE_SUBMIT,
)
from apps.ticket.models import Ticket, TicketTransition


DEMO_PASSWORD = "Demo@123456"

DEMO_USERS = [
    ("demo_creator", "提单用户", False),
    ("demo_ops_a", "运维甲", True),
    ("demo_ops_b", "运维乙", True),
    ("demo_dev", "开发审核", True),
]


class Command(BaseCommand):
    help = "模拟演示数据（用户/值班/工单），默认幂等；--purge 会删除 OM-DEMO-* 工单后再写入。"

    def add_arguments(self, parser):
        parser.add_argument(
            "--purge",
            action="store_true",
            help="删除 ticket_no 以 OM-DEMO- 开头的工单及其关联数据后再写入",
        )
        parser.add_argument(
            "--no-bootstrap",
            action="store_true",
            help="跳过自动执行 bootstrap_gaussdbom（若你已知基础数据已就绪）",
        )

    def handle(self, *args, **options):
        if not options["no_bootstrap"]:
            call_command("bootstrap_gaussdbom")
            self.stdout.write("已确保 bootstrap_gaussdbom 执行完成。")

        if options["purge"]:
            qs = Ticket.objects.filter(ticket_no__startswith="OM-DEMO-")
            n = qs.count()
            qs.delete()
            self.stdout.write(self.style.WARNING(f"已删除演示工单 {n} 条。"))

        users = self._ensure_users()
        kernel_sched = DutySchedule.objects.get(schedule_code="kernel-main")
        self._ensure_duty_members(kernel_sched, [users["demo_ops_a"], users["demo_ops_b"]])
        group = SysOrgGroup.objects.filter(group_code="default-kernel").first()
        self._ensure_reviewer_whitelist(users["demo_dev"])

        specs = [
            (
                "OM-DEMO-0001",
                STAGE_SUBMIT,
                None,
                Ticket.SourceType.HCS,
                Ticket.IssueType.KERNEL,
                users["demo_creator"],
                "演示：待送审的 HCS 内核问题单。",
            ),
            (
                "OM-DEMO-0002",
                STAGE_REVIEW,
                users["demo_ops_a"],
                Ticket.SourceType.HCS,
                Ticket.IssueType.KERNEL,
                users["demo_creator"],
                "演示：问题审核中，当前处理人为运维甲。",
            ),
            (
                "OM-DEMO-0003",
                STAGE_OPS_ANALYSIS,
                users["demo_ops_b"],
                Ticket.SourceType.BU,
                Ticket.IssueType.CONTROL,
                users["demo_creator"],
                "演示：运维分析中（管控），当前处理人为运维乙。",
            ),
            (
                "OM-DEMO-0004",
                STAGE_DEV_ANALYSIS,
                users["demo_dev"],
                Ticket.SourceType.TEMP,
                Ticket.IssueType.KERNEL,
                users["demo_creator"],
                "演示：开发人员分析中，归属模块 kernel_sql 可走开发审核白名单。",
            ),
            (
                "OM-DEMO-0005",
                STAGE_REVIEW_CLOSE,
                users["demo_ops_a"],
                Ticket.SourceType.HCS,
                Ticket.IssueType.KERNEL,
                users["demo_creator"],
                "演示：待终审关闭（仍可点「确认关单」结束流程）。",
            ),
            (
                "OM-DEMO-0006",
                STAGE_OPS_ANALYSIS,
                users["demo_creator"],
                Ticket.SourceType.SELF,
                Ticket.IssueType.OTHER,
                users["demo_creator"],
                "演示：运维自提单，默认在运维分析且处理人为本人。",
            ),
        ]

        for row in specs:
            self._ensure_ticket(*row, creator_group=group)

        self.stdout.write(self.style.SUCCESS("演示数据已就绪。"))
        self.stdout.write(
            f"演示账号：{', '.join(u for u, _, _ in DEMO_USERS)} ，密码均为 {DEMO_PASSWORD}\n"
            "（demo_ops_a / demo_ops_b / demo_dev 为 staff，可进 /admin/）\n"
            "工单：OM-DEMO-0001 … 0006"
        )

    def _ensure_users(self):
        out = {}
        for username, display_name, is_staff in DEMO_USERS:
            u, created = SysUser.objects.get_or_create(
                username=username,
                defaults={
                    "email": f"{username}@demo.local",
                    "display_name": display_name,
                    "is_staff": is_staff,
                    "is_active": True,
                },
            )
            if not created:
                u.display_name = display_name
                u.is_staff = is_staff
                u.is_active = True
            u.email = f"{username}@demo.local"
            u.set_password(DEMO_PASSWORD)
            u.save()
            out[username] = u
        return out

    def _ensure_duty_members(self, schedule: DutySchedule, user_list):
        for i, user in enumerate(user_list):
            DutyScheduleMember.objects.update_or_create(
                schedule=schedule,
                user=user,
                defaults={
                    "order_no": i,
                    "weight": 1,
                    "status": "active",
                },
            )

    def _ensure_reviewer_whitelist(self, reviewer: SysUser):
        SysReviewerWhitelist.objects.update_or_create(
            review_type=SysReviewerWhitelist.ReviewType.DEV_AUDIT,
            module_code="kernel_sql",
            reviewer_user=reviewer,
            defaults={"status": "active"},
        )

    def _ensure_ticket(
        self,
        ticket_no: str,
        stage: str,
        assignee,
        source_type: str,
        issue_type: str,
        creator: SysUser,
        description: str,
        *,
        creator_group,
    ):
        t, created = Ticket.objects.get_or_create(
            ticket_no=ticket_no,
            defaults={
                "source_type": source_type,
                "current_stage_code": stage,
                "current_assignee": assignee,
                "creator_user": creator,
                "creator_group": creator_group,
                "issue_type": issue_type or "",
                "status": Ticket.TicketStatus.PROCESSING,
            },
        )
        if not created:
            return

        TicketTransition.objects.create(
            ticket=t,
            from_stage_code="",
            to_stage_code=stage,
            action_code="seed_demo",
            operator_user=creator,
            from_assignee=None,
            to_assignee=assignee,
            comment="seed_demo_data 初始化",
        )

        TicketFieldValue.objects.update_or_create(
            ticket=t,
            stage_code=stage,
            field_code="ticket_description",
            defaults={
                "field_value_text": description,
                "updated_by": creator,
            },
        )

        if stage in (STAGE_OPS_ANALYSIS, STAGE_DEV_ANALYSIS):
            TicketFieldValue.objects.update_or_create(
                ticket=t,
                stage_code=stage,
                field_code="problem_belong_module",
                defaults={
                    "field_value_text": "kernel_sql",
                    "updated_by": creator,
                },
            )
