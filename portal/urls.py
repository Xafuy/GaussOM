from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("duty/", views.duty_overview, name="duty_overview"),
    path("duty/leave/", views.leave_request, name="leave_request"),
]
