from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("", include("portal.urls")),
    path("tickets/", include("tickets.urls")),
    path("analytics/", include("analytics.urls")),
]
