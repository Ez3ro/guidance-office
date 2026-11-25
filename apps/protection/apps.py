from django.apps import AppConfig


class ProtectionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.protection"
    label = "protection"
    verbose_name = "Child protection (LRP)"

    def ready(self) -> None:
        from apps.audit.registry import register

        from . import signals  # noqa: F401
        from .models import (
            CaseParty,
            ConcernType,
            ProtectionCase,
            Referral,
            ReferralAgency,
            RiskAssessment,
        )

        register(ProtectionCase, CaseParty, RiskAssessment, Referral, ConcernType, ReferralAgency)
