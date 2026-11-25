from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_index, name="index"),
    path("view/<slug:key>/", views.report_view, name="report"),
    path("print/intake/<int:pk>/", views.intake_sheet, name="intake_sheet"),
    path(
        "print/risk-assessment/<int:pk>/<int:assessment_pk>/",
        views.risk_assessment_form,
        name="risk_assessment_form",
    ),
    path("print/fact-finding/<int:pk>/", views.fact_finding_report, name="fact_finding_report"),
    path(
        "print/call-slip/violation/<int:pk>/", views.call_slip_violation, name="call_slip_violation"
    ),
    path("print/call-slip/case/<int:pk>/", views.call_slip_case, name="call_slip_case"),
    path(
        "print/call-slip/protection/<int:pk>/",
        views.call_slip_protection,
        name="call_slip_protection",
    ),
    path("print/confiscation/<int:pk>/", views.confiscation_slip, name="confiscation_slip"),
    path("print/guidance-profile/<int:pk>/", views.guidance_profile_print, name="guidance_profile"),
]
