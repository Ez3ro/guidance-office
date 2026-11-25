from django.urls import path

from . import views

app_name = "interventions"

urlpatterns = [
    path("", views.PlanListView.as_view(), name="list"),
    path("new/", views.PlanCreateView.as_view(), name="create"),
    path("<int:pk>/", views.PlanDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.PlanUpdateView.as_view(), name="update"),
    path("<int:pk>/progress/", views.add_progress_note, name="add_progress"),
]
