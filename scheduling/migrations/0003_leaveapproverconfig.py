from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scheduling", "0002_identityrouterule"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeaveApproverConfig",
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
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                ("note", models.CharField(blank=True, max_length=255, verbose_name="说明")),
                (
                    "approver",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="leave_approver_configs",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="审批人",
                    ),
                ),
            ],
            options={
                "verbose_name": "请假审批人配置",
                "verbose_name_plural": "请假审批人配置",
                "ordering": ("sort_order", "id"),
                "unique_together": {("approver",)},
            },
        ),
    ]
