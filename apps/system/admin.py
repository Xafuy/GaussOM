from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    SysOrgGroup,
    SysPermission,
    SysReviewerWhitelist,
    SysRole,
    SysRolePermission,
    SysUser,
    SysUserGroupRole,
)


@admin.register(SysUser)
class SysUserAdmin(DjangoUserAdmin):
    list_display = (
        "username",
        "display_name",
        "email",
        "is_staff",
        "is_active",
        "user_status",
    )
    list_filter = ("is_staff", "is_superuser", "is_active", "user_status")
    search_fields = ("username", "display_name", "email")
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("扩展", {"fields": ("display_name", "phone", "user_status", "is_admin")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("扩展", {"fields": ("display_name", "phone", "user_status", "is_admin")}),
    )


class SysRolePermissionInline(admin.TabularInline):
    model = SysRolePermission
    extra = 0
    autocomplete_fields = ("permission",)


@admin.register(SysRole)
class SysRoleAdmin(admin.ModelAdmin):
    list_display = ("role_code", "role_name", "status")
    search_fields = ("role_code", "role_name")
    inlines = [SysRolePermissionInline]


@admin.register(SysPermission)
class SysPermissionAdmin(admin.ModelAdmin):
    list_display = ("perm_code", "perm_name", "resource_type")
    search_fields = ("perm_code", "perm_name")


@admin.register(SysOrgGroup)
class SysOrgGroupAdmin(admin.ModelAdmin):
    list_display = ("group_code", "group_name", "group_type", "parent_group", "status")
    search_fields = ("group_code", "group_name")
    autocomplete_fields = ("parent_group",)


@admin.register(SysUserGroupRole)
class SysUserGroupRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "group", "role", "is_primary_group")
    autocomplete_fields = ("user", "group", "role")


@admin.register(SysReviewerWhitelist)
class SysReviewerWhitelistAdmin(admin.ModelAdmin):
    list_display = ("review_type", "module_code", "reviewer_user", "status")
    list_filter = ("review_type", "status")
    autocomplete_fields = ("reviewer_user",)
