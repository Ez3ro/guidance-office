from __future__ import annotations

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel
from apps.core.roles import Cap


class InterventionType(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class InterventionPlanQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user.has_cap(Cap.VIEW_INTERVENTIONS):
            return self
        return self.filter(responsible=user)


class InterventionPlan(TimeStampedModel):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ONGOING = "ongoing", "Ongoing"
        COMPLETED = "completed", "Completed"
        DISCONTINUED = "discontinued", "Discontinued"

    class Outcome(models.TextChoices):
        NOT_ASSESSED = "", "Not yet assessed"
        IMPROVED = "improved", "Improved"
        PARTIAL = "partial", "Partially improved"
        NO_CHANGE = "no_change", "No change"
        WORSENED = "worsened", "Worsened"

    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="interventions"
    )
    intervention_type = models.ForeignKey(
        InterventionType, on_delete=models.PROTECT, related_name="plans"
    )
    title = models.CharField(
        max_length=200, help_text="Short description without the learner's name."
    )
    goals = EncryptedTextField("Goals and indicators of progress")
    start_date = models.DateField(default=timezone.localdate)
    target_end_date = models.DateField("Review date", null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    responsible = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interventions_responsible",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PLANNED)
    outcome = models.CharField(max_length=20, choices=Outcome.choices, blank=True, default="")
    outcome_notes = EncryptedTextField(blank=True)
    protection_case = models.ForeignKey(
        "protection.ProtectionCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interventions",
    )
    disciplinary_case = models.ForeignKey(
        "discipline.DisciplinaryCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interventions",
    )
    violation = models.ForeignKey(
        "discipline.ViolationRecord",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="interventions",
    )

    objects = InterventionPlanQuerySet.as_manager()

    class Meta:
        ordering = ["-start_date", "-created_at"]

    def __str__(self) -> str:
        return self.title

    def audit_repr(self) -> str:
        return f"Intervention plan #{self.pk} (learner #{self.student_id})"

    def get_absolute_url(self) -> str:
        return reverse("interventions:detail", args=[self.pk])

    def user_can_view(self, user) -> bool:
        return user.has_cap(Cap.VIEW_INTERVENTIONS) or self.responsible_id == user.pk

    def user_can_edit(self, user) -> bool:
        return user.has_cap(Cap.MANAGE_INTERVENTIONS) or self.responsible_id == user.pk


class InterventionProgress(models.Model):
    plan = models.ForeignKey(
        InterventionPlan, on_delete=models.CASCADE, related_name="progress_notes"
    )
    date = models.DateField(default=timezone.localdate)
    note = EncryptedTextField()
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date", "-created_at"]
        verbose_name = "progress note"

    def __str__(self) -> str:
        return f"Progress note {self.date:%b %d, %Y}"

    def audit_repr(self) -> str:
        return f"Progress note on intervention #{self.plan_id}"
