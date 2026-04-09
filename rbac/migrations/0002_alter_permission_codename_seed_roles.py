from django.db import migrations, models


def seed_rbac(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")

    perm_specs = [
        ("ticket:advance", "推进工单阶段", "将工单推进到下一流程阶段"),
        ("ticket:transfer", "转派处理人", "变更工单当前处理人"),
        ("ticket:edit_fields", "编辑阶段字段", "保存当前阶段的表单字段"),
    ]
    perms = {}
    for codename, name, desc in perm_specs:
        p, _ = Permission.objects.get_or_create(
            codename=codename, defaults={"name": name, "description": desc}
        )
        perms[codename] = p

    all_three = list(perms.values())
    transfer_edit = [perms["ticket:transfer"], perms["ticket:edit_fields"]]

    role_specs = [
        ("流程负责人（PL）", "pl", "全流程操作", all_three),
        ("运维", "ops", "处理与流转", all_three),
        ("开发", "dev", "处理与流转", all_three),
        ("管控", "control", "同运维默认包", all_three),
        ("BU", "bu", "转派与填报（默认不含推进）", transfer_edit),
        ("访客", "guest", "只读（无工单写权限）", []),
    ]
    for name, slug, desc, perm_list in role_specs:
        role, _ = Role.objects.get_or_create(
            slug=slug, defaults={"name": name, "description": desc}
        )
        if perm_list:
            role.permissions.set(perm_list)


def unseed_rbac(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    Role.objects.filter(slug__in=["pl", "ops", "dev", "control", "bu", "guest"]).delete()
    Permission.objects.filter(
        codename__in=["ticket:advance", "ticket:transfer", "ticket:edit_fields"]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="permission",
            name="codename",
            field=models.CharField(
                help_text="如 ticket:advance，可含冒号",
                max_length=64,
                unique=True,
                verbose_name="编码",
            ),
        ),
        migrations.RunPython(seed_rbac, unseed_rbac),
    ]
