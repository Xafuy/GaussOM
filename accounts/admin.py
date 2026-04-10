from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    extra = 0
    max_num = 1
    verbose_name_plural = "扩展资料"


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)


admin.site.unregister(User)
admin.site.register(User, UserAdmin)
