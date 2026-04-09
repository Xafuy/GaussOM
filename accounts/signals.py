from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission as AuthPermission
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import UserProfile


@receiver(post_save, sender=get_user_model())
def ensure_profile_and_staff_admin_perms(sender, instance, created, **kwargs):
    UserProfile.objects.get_or_create(user=instance)

    # 约定：is_staff 用户可直接管理后台（不含 superuser 的全局越权）
    if instance.is_staff and instance.is_active:
        all_perms = AuthPermission.objects.all()
        instance.user_permissions.add(*all_perms)
