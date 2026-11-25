from django.apps import AppConfig


class CounselingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.counseling"
    label = "counseling"
    verbose_name = "Counseling"

    def ready(self) -> None:
        from apps.audit.registry import register

        from . import signals  # noqa: F401
        from .models import CounselingSession

        register(CounselingSession)
