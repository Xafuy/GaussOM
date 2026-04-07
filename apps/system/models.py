from django.contrib.auth.models import AbstractUser
from django.db import models


class SysUser(AbstractUser):
    """对应 ER 表 sys_user，扩展 Django 认证用户。"""

    display_name = models.CharField("显示名", max_length=100, blank=True)
    phone = models.CharField("手机号", max_length=32, blank=True)
    user_status = models.CharField(
        "账号状态",
        max_length=16,
        choices=[("active", "active"), ("inactive", "inactive")],
        default="active",
        db_index=True,
    )
    is_admin = models.BooleanField("业务管理员", default=False)

    class Meta:
        db_table = "sys_user"
        verbose_name = "用户"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.display_name or self.username


class SysOrgGroup(models.Model):
    class GroupType(models.TextChoices):
        KERNEL = "kernel", "内核"
        CONTROL = "control", "管控"
        PUBLIC_CLOUD = "public_cloud", "公有云"
        SPECIAL = "special", "专项"

    group_code = models.CharField("组编码", max_length=64, unique=True)
    group_name = models.CharField("组名称", max_length=128)
    group_type = models.CharField(
        "组类型", max_length=32, choices=GroupType.choices, default=GroupType.KERNEL
    )
    parent_group = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    status = models.CharField(
        "状态", max_length=16, default="active", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "sys_org_group"
        verbose_name = "组织/组"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.group_name


class SysRole(models.Model):
    role_code = models.CharField("角色编码", max_length=32, unique=True)
    role_name = models.CharField("角色名称", max_length=64)
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "sys_role"
        verbose_name = "角色"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.role_name


class SysPermission(models.Model):
    class ResourceType(models.TextChoices):
        MENU = "menu", "菜单"
        API = "api", "接口"
        BUTTON = "button", "按钮"
        DATA_SCOPE = "data_scope", "数据范围"

    perm_code = models.CharField("权限编码", max_length=128, unique=True)
    perm_name = models.CharField("权限名称", max_length=128)
    resource_type = models.CharField(
        "资源类型", max_length=32, choices=ResourceType.choices, default=ResourceType.API
    )

    class Meta:
        db_table = "sys_permission"
        verbose_name = "权限点"
        verbose_name_plural = verbose_name

    def __str__(self) -> str:
        return self.perm_name


class SysRolePermission(models.Model):
    role = models.ForeignKey(
        SysRole, on_delete=models.CASCADE, related_name="role_permissions"
    )
    permission = models.ForeignKey(
        SysPermission, on_delete=models.CASCADE, related_name="role_permissions"
    )

    class Meta:
        db_table = "sys_role_permission"
        unique_together = [("role", "permission")]
        verbose_name = "角色-权限"
        verbose_name_plural = verbose_name


class SysUserGroupRole(models.Model):
    user = models.ForeignKey(
        SysUser, on_delete=models.CASCADE, related_name="user_group_roles"
    )
    group = models.ForeignKey(
        SysOrgGroup, on_delete=models.CASCADE, related_name="user_group_roles"
    )
    role = models.ForeignKey(
        SysRole, on_delete=models.CASCADE, related_name="user_group_roles"
    )
    is_primary_group = models.BooleanField("是否主组", default=False)

    class Meta:
        db_table = "sys_user_group_role"
        unique_together = [("user", "group", "role")]
        verbose_name = "用户-组-角色"
        verbose_name_plural = verbose_name


class SysReviewerWhitelist(models.Model):
    class ReviewType(models.TextChoices):
        LEAVE = "leave", "请假审核"
        DEV_AUDIT = "dev_audit", "开发审核"
        CLOSE_AUDIT = "close_audit", "关闭审核"

    review_type = models.CharField(
        "审核类型", max_length=32, choices=ReviewType.choices, db_index=True
    )
    module_code = models.CharField("模块编码", max_length=64, blank=True)
    reviewer_user = models.ForeignKey(
        SysUser, on_delete=models.CASCADE, related_name="reviewer_whitelists"
    )
    status = models.CharField(max_length=16, default="active")

    class Meta:
        db_table = "sys_reviewer_whitelist"
        verbose_name = "审核白名单"
        verbose_name_plural = verbose_name
