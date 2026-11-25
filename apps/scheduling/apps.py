from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.scheduling"
    label = "scheduling"
    verbose_name = "Calendar and follow-ups"

    def ready(self) -> None:
        from apps.audit.registry import register

        from .models import CalendarEvent, FollowUp

        register(CalendarEvent, FollowUp)
