from django.db import migrations, models
import django.db.models.deletion


def seed_role_route_rules(apps, schema_editor):
    Role = apps.get_model("rbac", "Role")
    IdentityRouteRule = apps.get_model("scheduling", "IdentityRouteRule")
    RoleRouteRule = apps.get_model("scheduling", "RoleRouteRule")

    identity_to_role = {
        "bu": "bu",
        "control": "control",
        "ops": "ops",
        "dev": "dev",
    }
    for old in IdentityRouteRule.objects.all():
        role_slug = identity_to_role.get(old.identity)
        if not role_slug:
            continue
        role = Role.objects.filter(slug=role_slug).first()
        if not role:
            continue
        RoleRouteRule.objects.update_or_create(
            role=role,
            time_window=old.time_window,
            priority=old.priority,
            defaults={
                "rota_table_id": old.rota_table_id,
                "duty_sheet_id": old.duty_sheet_id,
                "is_active": old.is_active,
                "note": old.note,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0007_hcs_submit_stage_rule"),
        ("scheduling", "0003_leaveapproverconfig"),
    ]

    operations = [
        migrations.CreateModel(
            name="RoleRouteRule",
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
                    "time_window",
                    models.CharField(
                        choices=[("day", "工作日白天"), ("night", "晚间/节假日")],
                        max_length=16,
                        verbose_name="时间窗口",
                    ),
                ),
                ("priority", models.PositiveIntegerField(default=100, verbose_name="优先级")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("note", models.CharField(blank=True, max_length=255, verbose_name="说明")),
                (
                    "duty_sheet",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="role_routes",
                        to="scheduling.dutysheet",
                        verbose_name="命中值班表",
                    ),
                ),
                (
                    "role",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedule_route_rules",
                        to="rbac.role",
                        verbose_name="角色",
                    ),
                ),
                (
                    "rota_table",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="role_routes",
                        to="scheduling.rotatable",
                        verbose_name="命中轮值表",
                    ),
                ),
            ],
            options={
                "verbose_name": "角色分单路由规则",
                "verbose_name_plural": "角色分单路由规则",
                "ordering": ("priority", "id"),
                "unique_together": {("role", "time_window", "priority")},
            },
        ),
        migrations.RunPython(seed_role_route_rules, migrations.RunPython.noop),
    ]
