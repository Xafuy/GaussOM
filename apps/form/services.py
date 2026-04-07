"""动态表单：读取已发布 Schema + 阶段绑定，校验与保存。"""

from django.contrib.auth import get_user_model

from apps.form.models import (
    FieldDefinition,
    FormSchema,
    StageFieldBinding,
    TicketFieldValue,
)
from apps.ticket.models import Ticket

User = get_user_model()


def get_published_schema():
    return (
        FormSchema.objects.filter(status=FormSchema.SchemaStatus.PUBLISHED)
        .order_by("-published_at", "-id")
        .first()
    )


def bindings_for_stage(schema: FormSchema, stage_code: str):
    return (
        StageFieldBinding.objects.filter(schema=schema, stage_code=stage_code)
        .select_related("field", "field__option_set")
        .order_by("display_order", "id")
    )


def get_field_values_map(ticket: Ticket, stage_code: str):
    rows = TicketFieldValue.objects.filter(ticket=ticket, stage_code=stage_code)
    return {r.field_code: r.field_value_text or "" for r in rows}


def validate_and_save_stage(
    ticket: Ticket,
    stage_code: str,
    post_data,
    user: User,
):
    schema = get_published_schema()
    if not schema:
        return True, []
    errors = []
    bindings = list(bindings_for_stage(schema, stage_code))
    for b in bindings:
        f = b.field
        key = f"f_{f.field_code}"
        raw = post_data.get(key, "")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        raw = (raw or "").strip()
        if b.is_required and not raw:
            errors.append(f"{f.field_name} 为必填项")
    if errors:
        return False, errors

    for b in bindings:
        f = b.field
        key = f"f_{f.field_code}"
        raw = post_data.get(key, "")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        raw = raw or ""
        TicketFieldValue.objects.update_or_create(
            ticket=ticket,
            stage_code=stage_code,
            field_code=f.field_code,
            defaults={
                "field_value_text": raw.strip(),
                "field_value_json": None,
                "updated_by": user,
            },
        )
    return True, []


def options_for_field(field: FieldDefinition):
    if not field.option_set_id:
        return []
    return [
        (it.option_value, it.option_label)
        for it in field.option_set.items.filter(status="active").order_by(
            "order_no", "id"
        )
    ]
