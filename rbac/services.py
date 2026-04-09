from .models import StagePermissionRule, UserRole


def has_permission(user, codename):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return UserRole.objects.filter(
        user=user,
        role__permissions__codename=codename,
    ).exists()


STAGE_ROLE_MAP = {
    "issue_review": {"control", "ops", "pl"},
    "ops_analysis": {"ops", "pl"},
    "dev_analysis": {"dev", "pl"},
    "dev_review": {"pl"},
    "ops_closure": {"ops", "pl"},
    "audit_close": {"control", "pl"},
}


CREATE_TICKET_IDENTITIES = {"bu", "control", "ops"}


def user_role_codes(user):
    if not getattr(user, "is_authenticated", False):
        return set()
    return set(
        UserRole.objects.filter(user=user).values_list("role__slug", flat=True)
    )


def can_handle_stage(user, stage):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    configured_roles = set(
        StagePermissionRule.objects.filter(stage=stage, is_active=True).values_list(
            "role__slug", flat=True
        )
    )
    required_roles = configured_roles or STAGE_ROLE_MAP.get(stage, set())
    return bool(user_role_codes(user) & required_roles)


def can_create_ticket(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    profile = getattr(user, "profile", None)
    if not profile:
        return False
    identities = {s.strip().lower() for s in profile.identity_list() if s.strip()}
    return bool(identities & CREATE_TICKET_IDENTITIES)
