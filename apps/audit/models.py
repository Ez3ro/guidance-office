from django.conf import settings
from django.db import models
from django.utils import timezone


class ImmutableAuditError(Exception):
    pass


class AuditEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ImmutableAuditError("Audit events can't be changed.")

    def delete(self):
        raise ImmutableAuditError("Audit events can't be deleted.")


class AuditEvent(models.Model):
    """Append-only record of who did what, when and from where.

    Rows can't be updated or deleted through Django, and on PostgreSQL a trigger
    blocks UPDATE/DELETE at the database level too (see migration 0002).
    """

    class Action(models.TextChoices):
        CREATE = "create", "Created"
        UPDATE = "update", "Updated"
        DELETE = "delete", "Deleted"
        VIEW = "view", "Viewed"
        EXPORT = "export", "Exported"
        PRINT = "print", "Printed"
        DOWNLOAD = "download", "Downloaded"
        LOGIN = "login", "Signed in"
        LOGOUT = "logout", "Signed out"
        LOGIN_FAILED = "login_failed", "Failed sign-in"
        SYSTEM = "system", "System"

    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    actor_username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=Action.choices, db_index=True)
    model_label = models.CharField(max_length=100, blank=True, db_index=True)
    object_id = models.CharField(max_length=64, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    path = models.CharField(max_length=255, blank=True)

    objects = AuditEventQuerySet.as_manager()

    class Meta:
        ordering = ["-timestamp", "-id"]
        indexes = [models.Index(fields=["model_label", "object_id"])]

    def __str__(self) -> str:
        return f"{self.timestamp:%Y-%m-%d %H:%M} {self.actor_username or 'system'} {self.action} {self.object_repr}"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ImmutableAuditError("Audit events can't be changed.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableAuditError("Audit events can't be deleted.")

    @property
    def model_name(self) -> str:
        from django.apps import apps

        if not self.model_label:
            return ""
        try:
            return apps.get_model(self.model_label)._meta.verbose_name.title()
        except (LookupError, ValueError):
            return self.model_label
