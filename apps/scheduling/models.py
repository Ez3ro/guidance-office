from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel
from apps.core.roles import Cap


class CalendarEventQuerySet(models.QuerySet):
    def visible_to(self, user):
        condition = (
            Q(created_by=user) | Q(participants=user) | Q(visibility=CalendarEvent.Visibility.STAFF)
        )
        if user.has_cap(Cap.COUNSELING, Cap.VIEW_LRP):
            condition |= Q(visibility=CalendarEvent.Visibility.GUIDANCE)
        return self.filter(condition).distinct()


class CalendarEvent(TimeStampedModel):
    class EventType(models.TextChoices):
        PARENT_CONFERENCE = "parent_conference", "Parent / guardian conference"
        CASE_CONFERENCE = "case_conference", "Case conference"
        CPC_MEETING = "cpc_meeting", "CPC meeting"
        HOME_VISIT = "home_visit", "Home visitation"
        GUIDANCE_ACTIVITY = "guidance_activity", "Guidance program / activity"
        OTHER = "other", "Other"

    class Visibility(models.TextChoices):
        PRIVATE = "private", "Only me and the participants"
        GUIDANCE = "guidance", "Guidance office and CPC"
        STAFF = "staff", "All staff"

    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=30, choices=EventType.choices, default=EventType.OTHER)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    description = EncryptedTextField(blank=True)
    visibility = models.CharField(
        max_length=20, choices=Visibility.choices, default=Visibility.GUIDANCE
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, blank=True, related_name="calendar_events"
    )
    students = models.ManyToManyField(
        "students.Student", blank=True, related_name="calendar_events"
    )

    objects = CalendarEventQuerySet.as_manager()

    class Meta:
        ordering = ["start"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("scheduling:event_detail", args=[self.pk])

    def user_can_view(self, user) -> bool:
        return CalendarEvent.objects.visible_to(user).filter(pk=self.pk).exists()

    def user_can_edit(self, user) -> bool:
        return self.created_by_id == user.pk or user.has_cap(Cap.COUNSELING)


class FollowUpQuerySet(models.QuerySet):
    def open(self):
        return self.filter(status=FollowUp.Status.OPEN)

    def overdue(self):
        return self.open().filter(due_at__lt=timezone.now())

    def visible_to(self, user):
        condition = Q(assigned_to=user) | Q(created_by=user)
        for module, cap in FollowUp.MODULE_CAPS.items():
            if user.has_cap(cap):
                condition |= Q(module=module, restricted=False)
        if user.has_cap(Cap.VIEW_RESTRICTED_LRP):
            condition |= Q(restricted=True)
        return self.filter(condition)


class FollowUp(TimeStampedModel):
    """A dated task. Created by hand or automatically from DepEd deadlines."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    class Module(models.TextChoices):
        GENERAL = "general", "General"
        LRP = "lrp", "Learner rights and protection"
        DISCIPLINE = "discipline", "Discipline"
        COUNSELING = "counseling", "Counseling"
        INTERVENTION = "intervention", "Intervention"

    MODULE_CAPS = {
        Module.LRP: Cap.VIEW_LRP,
        Module.DISCIPLINE: Cap.VIEW_DISCIPLINE,
        Module.COUNSELING: Cap.COUNSELING,
        Module.INTERVENTION: Cap.VIEW_INTERVENTIONS,
    }

    title = models.CharField(max_length=255)
    notes = EncryptedTextField(blank=True)
    due_at = models.DateTimeField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="follow_ups",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.NORMAL)
    module = models.CharField(max_length=20, choices=Module.choices, default=Module.GENERAL)
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="follow_ups",
    )
    content_type = models.ForeignKey(ContentType, null=True, blank=True, on_delete=models.SET_NULL)
    object_id = models.PositiveBigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    # Set on follow-ups created from a DepEd deadline rule, e.g. "lrp.intake_48h".
    rule_key = models.CharField(max_length=60, blank=True)
    # Mirrors a restricted protection case: only the assignee and restricted-case staff see it.
    restricted = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    objects = FollowUpQuerySet.as_manager()

    class Meta:
        ordering = ["status", "due_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["content_type", "object_id", "rule_key"],
                condition=~Q(rule_key=""),
                name="unique_rule_follow_up",
            )
        ]
        indexes = [models.Index(fields=["status", "due_at"])]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("scheduling:followup_update", args=[self.pk])

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.OPEN and self.due_at < timezone.now()

    @property
    def is_due_soon(self) -> bool:
        return (
            self.status == self.Status.OPEN
            and not self.is_overdue
            and self.due_at < timezone.now() + timedelta(days=2)
        )

    @property
    def state(self) -> str:
        if self.status != self.Status.OPEN:
            return self.status
        if self.is_overdue:
            return "overdue"
        if self.is_due_soon:
            return "due_soon"
        return "open"

    @property
    def related_url(self) -> str | None:
        target = self.related
        return target.get_absolute_url() if target is not None else None

    def user_can_view(self, user) -> bool:
        return FollowUp.objects.visible_to(user).filter(pk=self.pk).exists()

    def user_can_edit(self, user) -> bool:
        return self.user_can_view(user)

    def mark_done(self, user=None) -> None:
        self.status = self.Status.DONE
        self.completed_at = timezone.now()
        self.completed_by = user
        self.save()
