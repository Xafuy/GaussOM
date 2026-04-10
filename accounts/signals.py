from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(pre_save, sender=get_user_model())
def cache_previous_is_staff(sender, instance, **kwargs):
    """供 post_save 判断是否为「新成为 staff」，避免每次保存都覆盖管理员在后台调整的权限。"""
    if instance.pk:
        row = (
            get_user_model()
            .objects.filter(pk=instance.pk)
            .values_list("is_staff", flat=True)
            .first()
        )
        instance._previous_is_staff = bool(row) if row is not None else None
    else:
        instance._previous_is_staff = None


@receiver(post_save, sender=get_user_model())
def ensure_profile_and_staff_admin_perms(sender, instance, **kwargs):
    """
    管理后台「新增用户」会先保存 User，再保存 UserProfile 内联。
    若在此处同步 get_or_create(UserProfile)，会与内联 INSERT 争抢 OneToOne，报唯一约束错误。
    将资料补全推迟到事务提交后，内联已写入则 get_or_create 仅命中；无内联数据则再补一行。
    """
    if kwargs.get("raw"):
        return

    user_id = instance.pk

    def ensure_profile():
        if not user_id:
            return
        u = get_user_model().objects.filter(pk=user_id).first()
        if u:
            UserProfile.objects.get_or_create(user=u)

    transaction.on_commit(ensure_profile)

    # 仅在「新建且为 staff」或「由非 staff 改为 staff」时授予全部 Django 管理权限；
    # 已为 staff 的后续保存不再覆盖，以便在后台单独增删权限。
    if instance.is_staff and instance.is_active:
        created = kwargs.get("created", False)
        prev = getattr(instance, "_previous_is_staff", None)
        should_grant_all = created or (prev is False)
        if should_grant_all:
            instance.user_permissions.set(Permission.objects.all())
