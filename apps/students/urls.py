from django.urls import path

from . import views

app_name = "students"

urlpatterns = [
    path("", views.StudentListView.as_view(), name="list"),
    path("new/", views.StudentCreateView.as_view(), name="create"),
    path("sections/", views.SectionListView.as_view(), name="sections"),
    path("<int:pk>/", views.StudentDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.StudentUpdateView.as_view(), name="update"),
    path("<int:pk>/timeline/", views.student_timeline, name="timeline"),
]
