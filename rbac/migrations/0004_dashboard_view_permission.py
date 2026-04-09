from django.db import migrations


def seed_dashboard_perm(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    perm, _ = Permission.objects.get_or_create(
        codename="dashboard:view",
        defaults={
            "name": "查看统计分析",
            "description": "访问 Dashboard 统计图表页面",
        },
    )
    for slug in ["pl", "ops", "control"]:
        role = Role.objects.filter(slug=slug).first()
        if role:
            role.permissions.add(perm)


def unseed_dashboard_perm(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Permission.objects.filter(codename="dashboard:view").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0003_stagepermissionrule"),
    ]

    operations = [
        migrations.RunPython(seed_dashboard_perm, unseed_dashboard_perm),
    ]
