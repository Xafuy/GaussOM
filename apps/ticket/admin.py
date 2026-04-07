from django.contrib import admin

from apps.ticket.models import (
    Ticket,
    TicketAssigneeHistory,
    TicketOperationLog,
    TicketStageDef,
    TicketTransition,
)


class TicketTransitionInline(admin.TabularInline):
    model = TicketTransition
    extra = 0
    readonly_fields = ("created_at",)
    autocomplete_fields = ("operator_user", "from_assignee", "to_assignee")


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = (
        "ticket_no",
        "current_stage_code",
        "status",
        "source_type",
        "issue_type",
        "current_assignee",
        "creator_user",
        "created_at",
    )
    list_filter = ("status", "current_stage_code", "source_type")
    search_fields = ("ticket_no",)
    autocomplete_fields = ("creator_user", "current_assignee", "creator_group")
    inlines = [TicketTransitionInline]


@admin.register(TicketStageDef)
class TicketStageDefAdmin(admin.ModelAdmin):
    list_display = ("stage_code", "stage_name", "stage_order", "status")
    ordering = ("stage_order",)


@admin.register(TicketTransition)
class TicketTransitionAdmin(admin.ModelAdmin):
    list_display = ("ticket", "action_code", "from_stage_code", "to_stage_code", "operator_user", "created_at")
    list_filter = ("action_code", "to_stage_code")
    autocomplete_fields = ("ticket", "operator_user", "from_assignee", "to_assignee")


@admin.register(TicketAssigneeHistory)
class TicketAssigneeHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "stage_code", "assignee_user", "assign_type", "assigned_at")
    autocomplete_fields = ("ticket", "assignee_user")


@admin.register(TicketOperationLog)
class TicketOperationLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "operation_type", "operator_user", "created_at")
    autocomplete_fields = ("ticket", "operator_user")
