from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = f"{settings.SITE_NAME} – settings"
admin.site.site_title = settings.SITE_NAME
admin.site.index_title = "Reference data and school settings"

urlpatterns = [
    path("", include("apps.core.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("students/", include("apps.students.urls")),
    path("discipline/", include("apps.discipline.urls")),
    path("counseling/", include("apps.counseling.urls")),
    path("interventions/", include("apps.interventions.urls")),
    path("protection/", include("apps.protection.urls")),
    path("calendar/", include("apps.scheduling.urls")),
    path("reports/", include("apps.reports.urls")),
    path("audit/", include("apps.audit.urls")),
    path("admin/", admin.site.urls),
]
