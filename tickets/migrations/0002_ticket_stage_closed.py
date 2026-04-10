from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ticket",
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
                default="hcs_submit",
                max_length=32,
                verbose_name="阶段",
            ),
        ),
    ]
