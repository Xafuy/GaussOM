from django.db import migrations, models


def seed_hcs_submit_rules(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    for slug in ("bu", "control", "ops", "pl"):
        role = Role.objects.filter(slug=slug).first()
        if not role:
            continue
        StagePermissionRule.objects.get_or_create(
            stage="hcs_submit",
            role=role,
            defaults={"is_active": True},
        )


def unseed_hcs_submit_rules(apps, schema_editor):
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    StagePermissionRule.objects.filter(stage="hcs_submit").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0006_stage_closed"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stagepermissionrule",
            name="stage",
            field=models.CharField(
                choices=[
                    ("hcs_submit", "HCS提单"),
                    ("issue_review", "问题审核"),
                    ("ops_analysis", "运维人员分析"),
                    ("dev_analysis", "开发人员分析"),
                    ("dev_review", "开发人员闭环"),
                    ("ops_closure", "运维人员闭环"),
                    ("audit_close", "问题审核关闭"),
                    ("closed", "问题单关闭"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="阶段",
            ),
        ),
        migrations.RunPython(seed_hcs_submit_rules, unseed_hcs_submit_rules),
    ]
