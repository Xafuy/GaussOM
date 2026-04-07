from django.contrib import admin

from apps.dispatch.models import (
    DispatchCompensationRecord,
    DispatchCursor,
    DispatchDecisionLog,
    DispatchPolicy,
    DispatchRule,
)


class DispatchRuleInline(admin.TabularInline):
    model = DispatchRule
    extra = 0


@admin.register(DispatchPolicy)
class DispatchPolicyAdmin(admin.ModelAdmin):
    list_display = ("policy_code", "policy_name", "status", "version_no")
    search_fields = ("policy_code", "policy_name")
    inlines = [DispatchRuleInline]


@admin.register(DispatchRule)
class DispatchRuleAdmin(admin.ModelAdmin):
    list_display = ("policy", "rule_code", "priority_no", "action_type", "status")
    list_filter = ("policy", "status")
    search_fields = ("rule_code", "action_type")


@admin.register(DispatchCursor)
class DispatchCursorAdmin(admin.ModelAdmin):
    list_display = ("schedule", "biz_scene", "current_member", "updated_at")


@admin.register(DispatchDecisionLog)
class DispatchDecisionLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "final_assignee", "created_at")
    autocomplete_fields = ("ticket", "final_assignee", "policy", "hit_rule")


@admin.register(DispatchCompensationRecord)
class DispatchCompensationRecordAdmin(admin.ModelAdmin):
    list_display = ("ticket", "transfer_type", "compensation_type", "status", "created_at")
    autocomplete_fields = ("ticket", "from_user", "to_user")
