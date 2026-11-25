from django.urls import path

from . import views

app_name = "discipline"

urlpatterns = [
    path("violations/", views.ViolationListView.as_view(), name="violations"),
    path("violations/new/", views.ViolationCreateView.as_view(), name="violation_create"),
    path("violations/<int:pk>/", views.ViolationDetailView.as_view(), name="violation_detail"),
    path("violations/<int:pk>/edit/", views.ViolationUpdateView.as_view(), name="violation_update"),
    path("cases/", views.CaseListView.as_view(), name="cases"),
    path("cases/new/", views.CaseCreateView.as_view(), name="case_create"),
    path("cases/<int:pk>/", views.CaseDetailView.as_view(), name="case_detail"),
    path("cases/<int:pk>/edit/", views.CaseUpdateView.as_view(), name="case_update"),
    path("cases/<int:pk>/sanctions/add/", views.add_sanction, name="add_sanction"),
]
