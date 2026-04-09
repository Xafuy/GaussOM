from django.contrib import admin

from .models import Permission, Role, StagePermissionRule, UserRole


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("codename", "name")
    search_fields = ("codename", "name")


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0
    raw_id_fields = ("user",)


class StagePermissionRuleInline(admin.TabularInline):
    model = StagePermissionRule
    extra = 0


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "slug")
    search_fields = ("name", "slug")
    filter_horizontal = ("permissions",)
    inlines = (UserRoleInline, StagePermissionRuleInline)


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    raw_id_fields = ("user",)


@admin.register(StagePermissionRule)
class StagePermissionRuleAdmin(admin.ModelAdmin):
    list_display = ("stage", "role", "is_active")
    list_filter = ("stage", "is_active", "role")
