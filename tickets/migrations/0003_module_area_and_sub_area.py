from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0002_ticket_stage_closed"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleArea",
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
                ("name", models.CharField(max_length=64, unique=True, verbose_name="一级模块")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
            ],
            options={
                "verbose_name": "问题模块一级",
                "verbose_name_plural": "问题模块一级",
                "ordering": ("sort_order", "id"),
            },
        ),
        migrations.CreateModel(
            name="ModuleSubArea",
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
                ("name", models.CharField(max_length=64, verbose_name="二级模块")),
                ("sort_order", models.PositiveIntegerField(default=0, verbose_name="排序")),
                ("is_active", models.BooleanField(default=True, verbose_name="启用")),
                (
                    "area",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sub_areas",
                        to="tickets.modulearea",
                        verbose_name="一级模块",
                    ),
                ),
            ],
            options={
                "verbose_name": "问题模块二级",
                "verbose_name_plural": "问题模块二级",
                "ordering": ("area__sort_order", "sort_order", "id"),
                "unique_together": {("area", "name")},
            },
        ),
    ]
