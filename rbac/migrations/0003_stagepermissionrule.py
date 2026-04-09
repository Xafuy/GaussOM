from django.db import migrations, models


def seed_stage_rules(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    defaults = {
        "issue_review": ["control", "ops", "pl"],
        "ops_analysis": ["ops", "pl"],
        "dev_analysis": ["dev", "pl"],
        "dev_review": ["pl"],
        "ops_closure": ["ops", "pl"],
        "audit_close": ["control", "pl"],
    }
    for stage, slugs in defaults.items():
        for slug in slugs:
            role = Role.objects.filter(slug=slug).first()
            if not role:
                continue
            StagePermissionRule.objects.get_or_create(
                stage=stage, role=role, defaults={"is_active": True}
            )


def unseed_stage_rules(apps, schema_editor):
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    StagePermissionRule.objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0002_alter_permission_codename_seed_roles"),
    ]

    operations = [
        migrations.CreateModel(
            name="StagePermissionRule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "stage",
                    models.CharField(
                        choices=[
                            ("issue_review", "问题审核"),
                            ("ops_analysis", "运维人员分析"),
                            ("dev_analysis", "开发人员分析"),
                            ("dev_review", "开发人员审核"),
                            ("ops_closure", "运维人员闭环"),
                            ("audit_close", "问题审核关闭"),
                        ],
                        db_index=True,
                        max_length=32,
                        verbose_name="阶段",
                    ),
                ),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="stage_rules",
                        to="rbac.role",
                        verbose_name="角色",
                    ),
                ),
            ],
            options={
                "verbose_name": "阶段处理权限规则",
                "verbose_name_plural": "阶段处理权限规则",
                "ordering": ("stage", "role__slug"),
                "unique_together": {("stage", "role")},
            },
        ),
        migrations.RunPython(seed_stage_rules, unseed_stage_rules),
    ]
