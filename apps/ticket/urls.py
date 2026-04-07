from django.urls import path

from apps.ticket import views

urlpatterns = [
    path("", views.TicketListView.as_view(), name="ticket_list"),
    path("new/", views.TicketCreateView.as_view(), name="ticket_create"),
    path("<int:pk>/", views.TicketDetailView.as_view(), name="ticket_detail"),
]
