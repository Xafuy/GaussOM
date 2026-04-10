from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from rbac.services import can_join_duty_rota

from .models import (
    DutyAssignment,
    DutySheet,
    LeaveApproverConfig,
    LeaveRequest,
    RoleRouteRule,
    RotaMember,
    RotaTable,
)


class RotaMemberAdminForm(forms.ModelForm):
    class Meta:
        model = RotaMember
        fields = "__all__"

    def clean_user(self):
        user = self.cleaned_data.get("user")
        if user and not can_join_duty_rota(user):
            raise ValidationError(
                "该用户须同时具备「运维人员分析」「运维人员闭环」阶段处理权限（按角色/阶段规则，不含 staff 豁免）。"
            )
        return user


class DutyAssignmentAdminForm(forms.ModelForm):
    class Meta:
        model = DutyAssignment
        fields = "__all__"

    def clean_user(self):
        user = self.cleaned_data.get("user")
        if user and not can_join_duty_rota(user):
            raise ValidationError(
                "该用户须同时具备「运维人员分析」「运维人员闭环」阶段处理权限（按角色/阶段规则，不含 staff 豁免）。"
            )
        return user


class RotaMemberInline(admin.TabularInline):
    model = RotaMember
    form = RotaMemberAdminForm
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
    form = DutyAssignmentAdminForm
    list_display = ("date", "sheet", "user")
    list_filter = ("sheet", "date")
    date_hierarchy = "date"
    raw_id_fields = ("user",)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("applicant", "leave_type", "start_at", "end_at", "status")
    list_filter = ("status", "leave_type")
    raw_id_fields = ("applicant", "approver")


@admin.register(LeaveApproverConfig)
class LeaveApproverConfigAdmin(admin.ModelAdmin):
    list_display = ("approver", "sort_order", "is_active", "note")
    list_filter = ("is_active",)
    list_editable = ("sort_order", "is_active", "note")
    raw_id_fields = ("approver",)


@admin.register(RoleRouteRule)
class RoleRouteRuleAdmin(admin.ModelAdmin):
    list_display = (
        "role",
        "time_window",
        "rota_table",
        "duty_sheet",
        "priority",
        "is_active",
    )
    list_filter = ("role", "time_window", "is_active")
    list_editable = ("priority", "is_active")
