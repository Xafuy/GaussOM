from django.contrib import admin

from apps.config_center.models import (
    ConfigAuditLog,
    ConfigItem,
    ConfigNamespace,
    ConfigPublishRecord,
    ConfigValue,
    ConfigVersion,
)


class ConfigItemInline(admin.TabularInline):
    model = ConfigItem
    extra = 0


@admin.register(ConfigNamespace)
class ConfigNamespaceAdmin(admin.ModelAdmin):
    list_display = ("namespace_code", "namespace_name", "status")
    search_fields = ("namespace_code", "namespace_name")
    inlines = [ConfigItemInline]


@admin.register(ConfigItem)
class ConfigItemAdmin(admin.ModelAdmin):
    list_display = ("namespace", "item_key", "item_name", "value_type", "status")
    list_filter = ("namespace", "value_type")
    search_fields = ("item_key", "item_name")


class ConfigValueInline(admin.TabularInline):
    model = ConfigValue
    extra = 0
    autocomplete_fields = ("config_item",)


@admin.register(ConfigVersion)
class ConfigVersionAdmin(admin.ModelAdmin):
    list_display = ("namespace", "version_no", "status", "published_at")
    list_filter = ("namespace", "status")
    search_fields = ("namespace__namespace_code", "version_no")
    inlines = [ConfigValueInline]
    autocomplete_fields = ("published_by",)


@admin.register(ConfigValue)
class ConfigValueAdmin(admin.ModelAdmin):
    list_display = ("version", "config_item")


@admin.register(ConfigPublishRecord)
class ConfigPublishRecordAdmin(admin.ModelAdmin):
    list_display = ("namespace", "from_version", "to_version", "operator_user", "created_at")
    autocomplete_fields = ("namespace", "from_version", "to_version", "operator_user")


@admin.register(ConfigAuditLog)
class ConfigAuditLogAdmin(admin.ModelAdmin):
    list_display = ("namespace", "item_key", "operator_user", "created_at")
    autocomplete_fields = ("namespace", "operator_user")
