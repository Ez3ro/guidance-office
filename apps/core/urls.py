from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("school-profile/", views.SchoolProfileUpdateView.as_view(), name="school_profile"),
    path(
        "attachments/<str:app_label>/<str:model>/<int:pk>/upload/",
        views.attachment_upload,
        name="attachment_upload",
    ),
    path("attachments/<int:pk>/download/", views.attachment_download, name="attachment_download"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
    path("internal/cron/daily/", views.cron_daily, name="cron_daily"),
]
