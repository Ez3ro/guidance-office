from django.urls import path

from . import views

app_name = "counseling"

urlpatterns = [
    path("", views.SessionListView.as_view(), name="list"),
    path("new/", views.SessionCreateView.as_view(), name="create"),
    path("<int:pk>/", views.SessionDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.SessionUpdateView.as_view(), name="update"),
]
