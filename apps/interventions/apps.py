from django.apps import AppConfig


class InterventionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.interventions"
    label = "interventions"
    verbose_name = "Interventions"

    def ready(self) -> None:
        from apps.audit.registry import register

        from . import signals  # noqa: F401
        from .models import InterventionPlan, InterventionProgress, InterventionType

        register(InterventionPlan, InterventionProgress, InterventionType)
