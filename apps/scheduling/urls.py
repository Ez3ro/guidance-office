from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("", views.calendar_month, name="calendar"),
    path("events/new/", views.EventCreateView.as_view(), name="event_create"),
    path("events/<int:pk>/", views.EventDetailView.as_view(), name="event_detail"),
    path("events/<int:pk>/edit/", views.EventUpdateView.as_view(), name="event_update"),
    path("follow-ups/", views.FollowUpListView.as_view(), name="followups"),
    path("follow-ups/new/", views.FollowUpCreateView.as_view(), name="followup_create"),
    path("follow-ups/<int:pk>/", views.FollowUpUpdateView.as_view(), name="followup_update"),
    path("follow-ups/<int:pk>/done/", views.followup_done, name="followup_done"),
]
