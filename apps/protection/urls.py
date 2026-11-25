from django.urls import path

from . import views

app_name = "protection"

urlpatterns = [
    path("", views.CaseListView.as_view(), name="list"),
    path("report/", views.report_concern, name="report"),
    path("my-reports/", views.MyReportsView.as_view(), name="my_reports"),
    path("new/", views.CaseCreateView.as_view(), name="create"),
    path("<int:pk>/", views.CaseDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.CaseUpdateView.as_view(), name="update"),
    path("<int:pk>/risk-assessment/", views.risk_assessment_create, name="risk_create"),
    path("<int:pk>/parties/add/", views.add_party, name="add_party"),
    path("<int:pk>/parties/<int:party_pk>/remove/", views.remove_party, name="remove_party"),
    path("<int:pk>/referrals/add/", views.add_referral, name="add_referral"),
    path("<int:pk>/referrals/<int:referral_pk>/", views.referral_update, name="referral_update"),
]
