from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from gaussdbom import views as web_views

urlpatterns = [
    path("healthz/", web_views.healthz, name="healthz"),
    path("readyz/", web_views.readyz, name="readyz"),
    path("admin/", admin.site.urls),
    path("", web_views.home, name="home"),
    path("dashboard/", web_views.dashboard, name="dashboard"),
    path("tickets/", include("apps.ticket.urls")),
    path("duty/", include("apps.duty.urls")),
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(template_name="registration/login.html"),
        name="login",
    ),
    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),
]

admin.site.site_header = "GaussDB 运维系统"
admin.site.site_title = "GaussDB OM"
