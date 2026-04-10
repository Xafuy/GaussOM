def nav_user_tags(request):
    if not request.user.is_authenticated:
        return {"nav_user_level": "", "nav_roles": "", "can_view_dashboard": False}

    if request.user.is_superuser:
        level = "超级用户"
    elif request.user.is_staff:
        level = "工作人员"
    else:
        level = "普通用户"

    roles = []
    if hasattr(request.user, "user_roles"):
        roles = [ur.role.name for ur in request.user.user_roles.select_related("role").all()]

    return {
        "nav_user_level": level,
        "nav_roles": "、".join(roles),
        "can_view_dashboard": bool(request.user.is_authenticated),
    }
