from django.urls import path

from apps.duty import views

urlpatterns = [
    path("", views.DutyScheduleListView.as_view(), name="duty_schedule_list"),
]
