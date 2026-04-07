from django.contrib import admin

from apps.form.models import (
    FieldDefinition,
    FieldOptionItem,
    FieldOptionSet,
    FieldRule,
    FormSchema,
    StageFieldBinding,
    TicketFieldValue,
)


class FieldOptionItemInline(admin.TabularInline):
    model = FieldOptionItem
    extra = 0


@admin.register(FieldOptionSet)
class FieldOptionSetAdmin(admin.ModelAdmin):
    list_display = ("option_set_code", "option_set_name", "status")
    inlines = [FieldOptionItemInline]


@admin.register(FieldDefinition)
class FieldDefinitionAdmin(admin.ModelAdmin):
    list_display = ("field_code", "field_name", "field_type", "option_set", "status")
    search_fields = ("field_code", "field_name")
    list_filter = ("field_type",)


class StageFieldBindingInline(admin.TabularInline):
    model = StageFieldBinding
    extra = 0
    autocomplete_fields = ("field",)


@admin.register(FormSchema)
class FormSchemaAdmin(admin.ModelAdmin):
    list_display = ("schema_code", "version_no", "schema_name", "status", "published_at")
    list_filter = ("status",)
    inlines = [StageFieldBindingInline]


@admin.register(StageFieldBinding)
class StageFieldBindingAdmin(admin.ModelAdmin):
    list_display = ("schema", "stage_code", "field", "is_required", "display_order")
    list_filter = ("stage_code", "schema")


@admin.register(FieldRule)
class FieldRuleAdmin(admin.ModelAdmin):
    list_display = ("schema", "stage_code", "rule_name", "status")
    list_filter = ("stage_code", "schema")


@admin.register(TicketFieldValue)
class TicketFieldValueAdmin(admin.ModelAdmin):
    list_display = ("ticket", "stage_code", "field_code", "updated_at")
    search_fields = ("field_code", "field_value_text")
    autocomplete_fields = ("ticket", "updated_by")
