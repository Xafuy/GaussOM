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
    "hcs_submit": {"bu", "control", "ops", "pl"},
    "issue_review": {"control", "ops", "pl"},
    "ops_analysis": {"ops", "pl"},
    "dev_analysis": {"dev", "pl"},
    "dev_review": {"pl"},
    "ops_closure": {"ops", "pl"},
    "audit_close": {"control", "pl"},
    "closed": {"control", "pl"},
}


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


def can_handle_stage_strict(user, stage):
    """阶段处理能力（不因 is_staff / is_superuser 豁免），用于排班成员资格等硬约束。"""
    if not getattr(user, "is_authenticated", False):
        return False
    configured_roles = set(
        StagePermissionRule.objects.filter(stage=stage, is_active=True).values_list(
            "role__slug", flat=True
        )
    )
    required_roles = configured_roles or STAGE_ROLE_MAP.get(stage, set())
    return bool(user_role_codes(user) & required_roles)


def can_join_duty_rota(user):
    """轮值/值班成员须同时具备「运维人员分析」「运维人员闭环」阶段处理能力。"""
    return can_handle_stage_strict(user, "ops_analysis") and can_handle_stage_strict(
        user, "ops_closure"
    )


def can_create_ticket(user):
    """提单入口权限：以「HCS提单」阶段能力为准（与 design/设计文档 一致，弱化独立 Permission）。"""
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_superuser or user.is_staff:
        return True
    return can_handle_stage(user, "hcs_submit")
