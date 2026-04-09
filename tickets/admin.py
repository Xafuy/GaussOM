from django.contrib import admin

from .models import Ticket, TicketTransitionLog


class TicketTransitionLogInline(admin.TabularInline):
    model = TicketTransitionLog
    extra = 0
    readonly_fields = ("from_stage", "to_stage", "operator", "note", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("number", "title", "stage", "reporter", "assignee", "created_at")
    list_filter = ("stage", "is_self_service")
    search_fields = ("title", "description", "number")
    raw_id_fields = ("reporter", "assignee")
    readonly_fields = ("number", "created_at", "updated_at")
    inlines = (TicketTransitionLogInline,)


@admin.register(TicketTransitionLog)
class TicketTransitionLogAdmin(admin.ModelAdmin):
    list_display = ("ticket", "from_stage", "to_stage", "operator", "created_at")
    list_filter = ("to_stage",)
