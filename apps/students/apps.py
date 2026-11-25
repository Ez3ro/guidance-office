from django.apps import AppConfig


class StudentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.students"
    label = "students"
    verbose_name = "Learners"

    def ready(self) -> None:
        from apps.audit.registry import register

        from .models import Enrollment, SchoolYear, Section, Student

        register(Student, Enrollment, SchoolYear, Section)
