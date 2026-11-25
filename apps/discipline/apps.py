from django.apps import AppConfig


class DisciplineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discipline"
    label = "discipline"
    verbose_name = "Discipline"

    def ready(self) -> None:
        from apps.audit.registry import register

        from . import signals  # noqa: F401
        from .models import (
            DisciplinaryCase,
            OffenseType,
            Sanction,
            SanctionApplied,
            ViolationRecord,
        )

        register(ViolationRecord, DisciplinaryCase, SanctionApplied, OffenseType, Sanction)
