from rbac.services import has_permission

IDENTITY_LABELS = {
    "bu": "BU",
    "control": "管控",
    "ops": "运维",
    "dev": "开发",
    "guest": "访客",
    "hcs": "HCS",
}


def nav_user_tags(request):
    if not request.user.is_authenticated:
        return {"nav_identities": "", "nav_roles": "", "can_view_dashboard": False}

    identities = []
    roles = []
    profile = getattr(request.user, "profile", None)
    if profile and profile.identities:
        for raw in profile.identity_list():
            identities.append(IDENTITY_LABELS.get(raw.lower(), raw))

    if hasattr(request.user, "user_roles"):
        roles = [ur.role.name for ur in request.user.user_roles.select_related("role").all()]

    return {
        "nav_identities": "、".join(identities),
        "nav_roles": ",".join(roles),
        "can_view_dashboard": has_permission(request.user, "dashboard:view"),
    }
