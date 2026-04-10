from django.db import migrations


def seed_ticket_extra_perms(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    specs = [
        ("ticket:create", "创建运维单", "允许创建新的运维单"),
        ("ticket:rollback", "回退运维单阶段", "允许将工单回退到上一阶段"),
    ]
    perms = {}
    for codename, name, desc in specs:
        p, _ = Permission.objects.get_or_create(
            codename=codename, defaults={"name": name, "description": desc}
        )
        perms[codename] = p

    for slug in ["pl", "ops", "control", "bu"]:
        role = Role.objects.filter(slug=slug).first()
        if role:
            role.permissions.add(perms["ticket:create"])
    for slug in ["pl", "ops", "control", "dev"]:
        role = Role.objects.filter(slug=slug).first()
        if role:
            role.permissions.add(perms["ticket:rollback"])


def unseed_ticket_extra_perms(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Permission.objects.filter(codename__in=["ticket:create", "ticket:rollback"]).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0004_dashboard_view_permission"),
    ]

    operations = [
        migrations.RunPython(seed_ticket_extra_perms, unseed_ticket_extra_perms),
    ]
