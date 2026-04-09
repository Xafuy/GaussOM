from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import UserProfile
from rbac.models import Role, UserRole
from scheduling.models import (
    DutyAssignment,
    DutySheet,
    IdentityRouteRule,
    LeaveRequest,
    OnCallStatus,
    RotaMember,
    RotaTable,
)
from tickets.models import Ticket, TicketStage, TicketTransitionLog
from tickets.stage_fields import get_field_defs_for_stage


def _set_stage_values(ticket, stage, payload):
    extra = ticket.extra_data or {}
    stage_fields = extra.get("stage_fields", {})
    current = stage_fields.get(stage, {})
    current.update(payload)
    stage_fields[stage] = current
    extra["stage_fields"] = stage_fields
    ticket.extra_data = extra
    ticket.save(update_fields=["extra_data", "updated_at"])


class Command(BaseCommand):
    help = "生成演示数据（用户、角色、排班、请假、工单）"

    def handle(self, *args, **options):
        with transaction.atomic():
            users = self._bootstrap_users()
            self._bootstrap_roles(users)
            self._bootstrap_schedule(users)
            self._bootstrap_tickets(users)

        self.stdout.write(self.style.SUCCESS("bootstrap_gaussdbom 完成。"))
        self.stdout.write("已确保 bootstrap_gaussdbom 执行完成。")
        self.stdout.write("演示数据已就绪。")
        self.stdout.write(
            "演示账号：demo_creator, demo_ops_a, demo_ops_b, demo_dev, demo_bu ... 密码均为 Demo@123456"
        )
        self.stdout.write("（多名演示用户为 staff，可进 /admin/）")
        self.stdout.write("工单：OM-DEMO-0001 … 0006")

    def _bootstrap_users(self):
        User = get_user_model()
        user_specs = [
            ("demo_creator", False, "访客", "张三"),
            ("demo_ops_a", True, "运维", "李炜"),
            ("demo_ops_b", True, "管控", "季超"),
            ("demo_dev", True, "开发", "刘强"),
            ("demo_bu", True, "BU", "任方博"),
            ("demo_ops_c", True, "运维", "娄静"),
            ("demo_ops_d", True, "运维", "张傲"),
            ("demo_control_b", True, "管控", "于子翔"),
            ("demo_dev_b", True, "开发", "崔乐然"),
        ]
        out = {}
        identity_map = {"访客": "guest", "运维": "ops", "开发": "dev", "管控": "control", "BU": "bu"}
        for username, is_staff, identity_cn, cn_name in user_specs:
            user, _ = User.objects.get_or_create(
                username=username,
                defaults={
                    "is_staff": is_staff,
                    "is_active": True,
                    "email": "%s@example.com" % username,
                },
            )
            user.is_staff = is_staff
            user.is_active = True
            user.first_name = cn_name
            user.set_password("Demo@123456")
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.identities = identity_map.get(identity_cn, "guest")
            profile.save()
            out[username] = user
        return out

    def _bootstrap_roles(self, users):
        mapping = {
            "demo_creator": "guest",
            "demo_ops_a": "ops",
            "demo_ops_b": "control",
            "demo_dev": "dev",
            "demo_bu": "bu",
            "demo_ops_c": "ops",
            "demo_ops_d": "ops",
            "demo_control_b": "control",
            "demo_dev_b": "dev",
        }
        for username, role_slug in mapping.items():
            role = Role.objects.filter(slug=role_slug).first()
            if role:
                UserRole.objects.get_or_create(user=users[username], role=role)

    def _bootstrap_schedule(self, users):
        rota, _ = RotaTable.objects.get_or_create(
            slug="day-default",
            defaults={"name": "白班默认轮值", "is_active": True},
        )
        for idx, uname in enumerate(["demo_ops_a", "demo_ops_c", "demo_ops_d", "demo_dev"]):
            RotaMember.objects.update_or_create(
                rota=rota,
                user=users[uname],
                defaults={
                    "sort_order": idx,
                    "status": OnCallStatus.ONLINE,
                    "active_ticket_count": 0,
                },
            )

        duty, _ = DutySheet.objects.get_or_create(
            slug="night-default",
            defaults={"name": "晚间节假日默认值班", "is_active": True},
        )
        bu_rota, _ = RotaTable.objects.get_or_create(
            slug="day-bu",
            defaults={"name": "BU白班轮值", "is_active": True},
        )
        control_rota, _ = RotaTable.objects.get_or_create(
            slug="day-control",
            defaults={"name": "管控白班轮值", "is_active": True},
        )
        bu_duty, _ = DutySheet.objects.get_or_create(
            slug="night-bu",
            defaults={"name": "BU夜间值班", "is_active": True},
        )
        control_duty, _ = DutySheet.objects.get_or_create(
            slug="night-control",
            defaults={"name": "管控夜间值班", "is_active": True},
        )
        kernel_duty, _ = DutySheet.objects.get_or_create(
            slug="night-kernel",
            defaults={"name": "内核夜间值班", "is_active": True},
        )
        today = timezone.localdate()
        for d in [today, today + timedelta(days=1)]:
            for uname in ["demo_ops_a", "demo_ops_c", "demo_ops_d"]:
                DutyAssignment.objects.get_or_create(
                    sheet=duty, date=d, user=users[uname]
                )
            DutyAssignment.objects.get_or_create(sheet=bu_duty, date=d, user=users["demo_ops_a"])
            DutyAssignment.objects.get_or_create(
                sheet=control_duty, date=d, user=users["demo_ops_b"]
            )
            DutyAssignment.objects.get_or_create(sheet=kernel_duty, date=d, user=users["demo_ops_d"])

        RotaMember.objects.get_or_create(
            rota=bu_rota,
            user=users["demo_ops_a"],
            defaults={
                "sort_order": 0,
                "status": OnCallStatus.ONLINE,
                "active_ticket_count": 0,
            },
        )
        RotaMember.objects.get_or_create(
            rota=control_rota,
            user=users["demo_ops_b"],
            defaults={
                "sort_order": 0,
                "status": OnCallStatus.ONLINE,
                "active_ticket_count": 0,
            },
        )
        public_rota, _ = RotaTable.objects.get_or_create(
            slug="day-public",
            defaults={"name": "公有云白班轮值", "is_active": True},
        )
        RotaMember.objects.get_or_create(
            rota=public_rota,
            user=users["demo_bu"],
            defaults={"sort_order": 0, "status": OnCallStatus.ONLINE, "active_ticket_count": 0},
        )

        IdentityRouteRule.objects.update_or_create(
            identity=IdentityRouteRule.Identity.BU,
            time_window=IdentityRouteRule.TimeWindow.DAY,
            priority=10,
            defaults={"rota_table": bu_rota, "duty_sheet": None, "is_active": True},
        )
        IdentityRouteRule.objects.update_or_create(
            identity=IdentityRouteRule.Identity.BU,
            time_window=IdentityRouteRule.TimeWindow.NIGHT,
            priority=10,
            defaults={"rota_table": None, "duty_sheet": bu_duty, "is_active": True},
        )
        IdentityRouteRule.objects.update_or_create(
            identity=IdentityRouteRule.Identity.CONTROL,
            time_window=IdentityRouteRule.TimeWindow.DAY,
            priority=10,
            defaults={
                "rota_table": control_rota,
                "duty_sheet": None,
                "is_active": True,
            },
        )
        IdentityRouteRule.objects.update_or_create(
            identity=IdentityRouteRule.Identity.CONTROL,
            time_window=IdentityRouteRule.TimeWindow.NIGHT,
            priority=10,
            defaults={
                "rota_table": None,
                "duty_sheet": control_duty,
                "is_active": True,
            },
        )

        now = timezone.now()
        LeaveRequest.objects.update_or_create(
            applicant=users["demo_ops_b"],
            leave_type="年假",
            start_at=now - timedelta(hours=4),
            end_at=now + timedelta(hours=10),
            defaults={
                "status": LeaveRequest.Status.APPROVED,
                "reason": "演示请假：用于验证分单跳过",
                "approver": users["demo_ops_a"],
                "cc": "demo_dev",
            },
        )

    def _bootstrap_tickets(self, users):
        creator = users["demo_creator"]
        ops_a = users["demo_ops_a"]
        dev = users["demo_dev"]

        existing = Ticket.objects.filter(title__startswith="OM-DEMO-").count()
        if existing >= 6:
            return

        now = timezone.now()

        # 1) HCS提单 -> 问题审核
        t1 = Ticket.objects.create(
            title="OM-DEMO-0001 分单演示单",
            description="用于展示自动分单到问题审核阶段",
            reporter=creator,
            assignee=ops_a,
            stage=TicketStage.ISSUE_REVIEW,
        )
        _set_stage_values(
            t1,
            TicketStage.HCS_SUBMIT,
            {
                "start_date": str((timezone.localdate() - timedelta(days=6))),
                "site": "深圳",
                "business_env": "生产环境（运维）",
                "severity": "一般",
                "problem_component": "内核问题",
                "issue_description": "自动分单演示",
            },
        )
        _set_stage_values(
            t1, TicketStage.ISSUE_REVIEW, {"issue_type_prejudge": "咨询类", "disposition": "确认问题"}
        )
        Ticket.objects.filter(pk=t1.pk).update(created_at=now - timedelta(days=6), updated_at=now - timedelta(days=6))
        TicketTransitionLog.objects.create(
            ticket=t1,
            from_stage=TicketStage.HCS_SUBMIT,
            to_stage=TicketStage.ISSUE_REVIEW,
            operator=creator,
            note="seed: 自动分单演示",
        )

        # 2) 运维分析
        t2 = Ticket.objects.create(
            title="OM-DEMO-0002 运维分析演示单",
            description="已推进到运维分析",
            reporter=creator,
            assignee=ops_a,
            stage=TicketStage.OPS_ANALYSIS,
        )
        _set_stage_values(
            t2,
            TicketStage.OPS_ANALYSIS,
            {
                "introduced_module": "连接管理",
                "owned_module": "内核事务",
                "is_quality_issue": "是",
                "issue_type": "性能",
                "severity": "严重",
                "site": "北京",
                "progress_tracking": "已定位初步线索",
            },
        )
        Ticket.objects.filter(pk=t2.pk).update(created_at=now - timedelta(days=5), updated_at=now - timedelta(days=4))
        TicketTransitionLog.objects.create(
            ticket=t2,
            from_stage=TicketStage.ISSUE_REVIEW,
            to_stage=TicketStage.OPS_ANALYSIS,
            operator=ops_a,
            note="seed: 已进入运维分析",
        )

        # 3) 开发分析
        t3 = Ticket.objects.create(
            title="OM-DEMO-0003 开发分析演示单",
            description="已转派开发并进入开发分析",
            reporter=creator,
            assignee=dev,
            stage=TicketStage.DEV_ANALYSIS,
        )
        _set_stage_values(
            t3,
            TicketStage.DEV_ANALYSIS,
            {
                "introduced_module": "存储引擎",
                "owned_module": "执行器",
                "is_quality_issue": "否",
                "issue_type": "稳定性",
                "severity": "致命",
                "site": "西安",
                "root_cause": "并发场景下缓存过期时序不一致",
                "progress_tracking": "开发已接手排查",
            },
        )
        Ticket.objects.filter(pk=t3.pk).update(created_at=now - timedelta(days=4), updated_at=now - timedelta(days=3))
        TicketTransitionLog.objects.create(
            ticket=t3,
            from_stage=TicketStage.OPS_ANALYSIS,
            to_stage=TicketStage.DEV_ANALYSIS,
            operator=ops_a,
            note="seed: 转派开发",
        )

        # 4) 开发审核
        t4 = Ticket.objects.create(
            title="OM-DEMO-0004 开发审核演示单",
            description="开发分析完成进入审核",
            reporter=creator,
            assignee=dev,
            stage=TicketStage.DEV_REVIEW,
        )
        _set_stage_values(
            t4,
            TicketStage.DEV_REVIEW,
            {"need_alert": "否", "business_impact": "中", "severity": "严重", "site": "上海"},
        )
        Ticket.objects.filter(pk=t4.pk).update(created_at=now - timedelta(days=3), updated_at=now - timedelta(days=2))
        TicketTransitionLog.objects.create(
            ticket=t4,
            from_stage=TicketStage.DEV_ANALYSIS,
            to_stage=TicketStage.DEV_REVIEW,
            operator=dev,
            note="seed: 开发审核中",
        )

        # 5) 运维闭环
        t5 = Ticket.objects.create(
            title="OM-DEMO-0005 运维闭环演示单",
            description="准备审核关闭",
            reporter=creator,
            assignee=ops_a,
            stage=TicketStage.OPS_CLOSURE,
        )
        _set_stage_values(
            t5,
            TicketStage.OPS_CLOSURE,
            {
                "involves_fault_recovery": "是",
                "severity": "事故",
                "site": "广州",
                "root_cause": "配置缺失导致连接中断",
                "external_reply": "已修复并复测通过",
            },
        )
        Ticket.objects.filter(pk=t5.pk).update(created_at=now - timedelta(days=2), updated_at=now - timedelta(days=1))
        TicketTransitionLog.objects.create(
            ticket=t5,
            from_stage=TicketStage.DEV_REVIEW,
            to_stage=TicketStage.OPS_CLOSURE,
            operator=ops_a,
            note="seed: 运维闭环处理中",
        )

        # 6) 已关闭
        t6 = Ticket.objects.create(
            title="OM-DEMO-0006 审核关闭演示单",
            description="闭环示例",
            reporter=creator,
            assignee=ops_a,
            stage=TicketStage.AUDIT_CLOSE,
        )
        _set_stage_values(
            t6,
            TicketStage.AUDIT_CLOSE,
            {"need_alert": "否", "business_impact": "低", "severity": "一般", "site": "深圳"},
        )
        Ticket.objects.filter(pk=t6.pk).update(created_at=now - timedelta(days=1), updated_at=now)
        TicketTransitionLog.objects.create(
            ticket=t6,
            from_stage=TicketStage.OPS_CLOSURE,
            to_stage=TicketStage.AUDIT_CLOSE,
            operator=ops_a,
            note="seed: 已审核关闭",
        )

        # 避免 stage_fields 结构为空，补齐每个工单当前阶段字段框架（便于展示）
        for t in [t1, t2, t3, t4, t5, t6]:
            defs = get_field_defs_for_stage(t.stage)
            if not defs:
                continue
            extra = t.extra_data or {}
            sf = extra.get("stage_fields", {})
            sf.setdefault(t.stage, {})
            extra["stage_fields"] = sf
            t.extra_data = extra
            t.save(update_fields=["extra_data", "updated_at"])
