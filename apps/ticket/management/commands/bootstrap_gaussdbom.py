from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.dispatch.models import DispatchPolicy
from apps.duty.models import DutySchedule
from apps.form.models import (
    FieldDefinition,
    FieldOptionItem,
    FieldOptionSet,
    FormSchema,
    StageFieldBinding,
)
from apps.system.models import SysOrgGroup
from apps.ticket.constants import ORDERED_STAGES, STAGE_LABELS
from apps.ticket.models import TicketStageDef


class Command(BaseCommand):
    help = "初始化阶段定义、默认表单 Schema、值班表骨架与分单策略占位（可重复执行，跳过已存在主键）。"

    def handle(self, *args, **options):
        self._seed_stages()
        self._seed_org()
        self._seed_duty_schedules()
        self._seed_dispatch_policy()
        self._seed_form_schema()
        self.stdout.write(self.style.SUCCESS("bootstrap_gaussdbom 完成。"))

    def _seed_stages(self):
        for i, code in enumerate(ORDERED_STAGES):
            TicketStageDef.objects.get_or_create(
                stage_code=code,
                defaults={
                    "stage_name": STAGE_LABELS.get(code, code),
                    "stage_order": i + 1,
                    "status": "active",
                },
            )

    def _seed_org(self):
        SysOrgGroup.objects.get_or_create(
            group_code="default-kernel",
            defaults={
                "group_name": "内核运维默认组",
                "group_type": SysOrgGroup.GroupType.KERNEL,
                "status": "active",
            },
        )

    def _seed_duty_schedules(self):
        DutySchedule.objects.get_or_create(
            schedule_code="kernel-main",
            defaults={
                "schedule_name": "内核大循环",
                "schedule_type": DutySchedule.ScheduleType.KERNEL,
                "applicable_day_type": DutySchedule.ApplicableDayType.ALL,
                "status": "active",
            },
        )
        DutySchedule.objects.get_or_create(
            schedule_code="control-main",
            defaults={
                "schedule_name": "管控值班表",
                "schedule_type": DutySchedule.ScheduleType.CONTROL,
                "applicable_day_type": DutySchedule.ApplicableDayType.ALL,
                "status": "active",
            },
        )

    def _seed_dispatch_policy(self):
        DispatchPolicy.objects.get_or_create(
            policy_code="default-v1",
            defaults={
                "policy_name": "默认分单策略（初版）",
                "status": "active",
                "version_no": 1,
            },
        )

    def _seed_form_schema(self):
        schema, created = FormSchema.objects.get_or_create(
            schema_code="gaussdbom-default",
            version_no=1,
            defaults={
                "schema_name": "GaussDB运维默认表单",
                "status": FormSchema.SchemaStatus.DRAFT,
            },
        )
        if created or schema.status != FormSchema.SchemaStatus.PUBLISHED:
            schema.status = FormSchema.SchemaStatus.PUBLISHED
            schema.published_at = timezone.now()
            schema.save(update_fields=["status", "published_at"])

        def ensure_field(code, name, ftype, option_set=None):
            obj, _ = FieldDefinition.objects.get_or_create(
                field_code=code,
                defaults={
                    "field_name": name,
                    "field_type": ftype,
                    "option_set": option_set,
                    "status": "active",
                },
            )
            if obj.field_name != name or obj.field_type != ftype:
                obj.field_name = name
                obj.field_type = ftype
                obj.option_set = option_set
                obj.save(update_fields=["field_name", "field_type", "option_set"])
            return obj

        mod_set, _ = FieldOptionSet.objects.get_or_create(
            option_set_code="problem-modules",
            defaults={"option_set_name": "问题归属模块示例", "status": "active"},
        )
        if not mod_set.items.exists():
            for i, (val, lab) in enumerate(
                [
                    ("kernel_sql", "SQL引擎"),
                    ("kernel_storage", "存储"),
                    ("control_plane", "管控面"),
                ]
            ):
                FieldOptionItem.objects.create(
                    option_set=mod_set,
                    option_value=val,
                    option_label=lab,
                    order_no=i,
                    status="active",
                )

        f_desc = ensure_field(
            "ticket_description",
            "问题描述",
            FieldDefinition.FieldType.RICH_TEXT,
        )
        f_module = ensure_field(
            "problem_belong_module",
            "问题归属模块",
            FieldDefinition.FieldType.SELECT,
            option_set=mod_set,
        )
        f_ops_note = ensure_field(
            "ops_analysis_note",
            "运维分析说明",
            FieldDefinition.FieldType.RICH_TEXT,
        )
        f_dev_note = ensure_field(
            "dev_analysis_note",
            "开发分析说明",
            FieldDefinition.FieldType.RICH_TEXT,
        )
        f_audit_note = ensure_field(
            "dev_audit_note",
            "开发审核意见",
            FieldDefinition.FieldType.RICH_TEXT,
        )
        f_close_note = ensure_field(
            "ops_close_note",
            "运维闭环说明",
            FieldDefinition.FieldType.RICH_TEXT,
        )
        f_final_note = ensure_field(
            "review_close_note",
            "终审关闭说明",
            FieldDefinition.FieldType.RICH_TEXT,
        )

        def bind(stage, field, order, req=False, vis=True):
            StageFieldBinding.objects.update_or_create(
                schema=schema,
                stage_code=stage,
                field=field,
                defaults={
                    "is_visible": vis,
                    "is_required": req,
                    "is_readonly": False,
                    "display_order": order,
                },
            )

        from apps.ticket.constants import (
            STAGE_DEV_ANALYSIS,
            STAGE_DEV_AUDIT,
            STAGE_OPS_ANALYSIS,
            STAGE_OPS_CLOSE,
            STAGE_REVIEW,
            STAGE_REVIEW_CLOSE,
            STAGE_SUBMIT,
        )

        bind(STAGE_SUBMIT, f_desc, 1, req=True)
        bind(STAGE_REVIEW, f_desc, 1, req=False)
        bind(STAGE_OPS_ANALYSIS, f_module, 1, req=False)
        bind(STAGE_OPS_ANALYSIS, f_ops_note, 2, req=False)
        bind(STAGE_DEV_ANALYSIS, f_module, 1, req=False)
        bind(STAGE_DEV_ANALYSIS, f_dev_note, 2, req=False)
        bind(STAGE_DEV_AUDIT, f_audit_note, 1, req=False)
        bind(STAGE_OPS_CLOSE, f_close_note, 1, req=False)
        bind(STAGE_REVIEW_CLOSE, f_final_note, 1, req=False)
