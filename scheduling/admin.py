from django.contrib import admin

from .models import (
    DutyAssignment,
    DutySheet,
    IdentityRouteRule,
    LeaveRequest,
    RotaMember,
    RotaTable,
)


class RotaMemberInline(admin.TabularInline):
    model = RotaMember
    extra = 0
    raw_id_fields = ("user",)


@admin.register(RotaTable)
class RotaTableAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    inlines = (RotaMemberInline,)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DutySheet)
class DutySheetAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(DutyAssignment)
class DutyAssignmentAdmin(admin.ModelAdmin):
    list_display = ("date", "sheet", "user")
    list_filter = ("sheet", "date")
    date_hierarchy = "date"
    raw_id_fields = ("user",)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("applicant", "leave_type", "start_at", "end_at", "status")
    list_filter = ("status", "leave_type")
    raw_id_fields = ("applicant", "approver")


@admin.register(IdentityRouteRule)
class IdentityRouteRuleAdmin(admin.ModelAdmin):
    list_display = (
        "identity",
        "time_window",
        "rota_table",
        "duty_sheet",
        "priority",
        "is_active",
    )
    list_filter = ("identity", "time_window", "is_active")
    list_editable = ("priority", "is_active")
