from django.contrib import admin

from apps.duty.models import (
    DutyCalendar,
    DutySchedule,
    DutyScheduleMember,
    DutySubstitution,
    LeaveApprovalRecord,
    LeaveRequest,
)


class DutyScheduleMemberInline(admin.TabularInline):
    model = DutyScheduleMember
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(DutySchedule)
class DutyScheduleAdmin(admin.ModelAdmin):
    list_display = ("schedule_code", "schedule_name", "schedule_type", "status")
    search_fields = ("schedule_code", "schedule_name")
    inlines = [DutyScheduleMemberInline]


@admin.register(DutyCalendar)
class DutyCalendarAdmin(admin.ModelAdmin):
    list_display = ("calendar_date", "day_type", "shift_type")


@admin.register(DutyScheduleMember)
class DutyScheduleMemberAdmin(admin.ModelAdmin):
    list_display = ("schedule", "user", "order_no", "status")
    list_filter = ("schedule", "status")
    autocomplete_fields = ("user", "schedule")


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "applicant_user", "approval_status", "start_time", "end_time")
    list_filter = ("approval_status",)
    search_fields = ("id", "applicant_user__username")
    autocomplete_fields = ("applicant_user",)


@admin.register(LeaveApprovalRecord)
class LeaveApprovalRecordAdmin(admin.ModelAdmin):
    list_display = ("leave_request", "reviewer_user", "action", "action_time")
    autocomplete_fields = ("reviewer_user", "leave_request")


@admin.register(DutySubstitution)
class DutySubstitutionAdmin(admin.ModelAdmin):
    list_display = ("schedule", "from_user", "to_user", "start_time", "status")
    autocomplete_fields = ("from_user", "to_user", "schedule")
