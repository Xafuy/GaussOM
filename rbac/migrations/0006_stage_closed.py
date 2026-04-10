from django.db import migrations, models


def seed_closed_rules(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    for slug in ("control", "pl"):
        role = Role.objects.filter(slug=slug).first()
        if not role:
            continue
        StagePermissionRule.objects.get_or_create(
            stage="closed", role=role, defaults={"is_active": True}
        )


def unseed_closed_rules(apps, schema_editor):
    StagePermissionRule = apps.get_model("rbac", "StagePermissionRule")
    StagePermissionRule.objects.filter(stage="closed").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0005_ticket_create_and_rollback_permission"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stagepermissionrule",
            name="stage",
            field=models.CharField(
                choices=[
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
        migrations.RunPython(seed_closed_rules, unseed_closed_rules),
    ]
