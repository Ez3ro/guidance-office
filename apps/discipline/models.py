from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel, next_reference
from apps.core.roles import Cap


class OffenseLevel(models.IntegerChoices):
    """Learner offence levels under DO 006, s. 2026 (Annex I)."""

    FIRST = 1, "First level"
    SECOND = 2, "Second level"
    THIRD = 3, "Third level"


class OffenseType(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    level = models.PositiveSmallIntegerField(choices=OffenseLevel.choices)
    description = models.TextField(blank=True)
    default_response = models.TextField(
        "Sanctions / interventions under the school's rules", blank=True
    )
    is_bullying = models.BooleanField(default=False)
    is_device_related = models.BooleanField(
        "Portable device violation",
        default=False,
        help_text="Uses the progressive sanctions in Annex G.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["level", "name"]

    def __str__(self) -> str:
        return f"{self.name} (L{self.level})"


class Sanction(models.Model):
    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    requires_due_process = models.BooleanField(
        default=False, help_text="Needs written notice, time to answer and a written decision."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DisciplinaryCaseQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user.has_cap(Cap.VIEW_DISCIPLINE):
            return self
        return self.none()

    def open(self):
        return self.exclude(
            status__in=[DisciplinaryCase.Status.CLOSED, DisciplinaryCase.Status.DISMISSED]
        )


class DisciplinaryCase(TimeStampedModel):
    """A case that may lead to a penalty, so DO 006 due process applies."""

    class Status(models.TextChoices):
        FILED = "filed", "Filed"
        NOTICE_SERVED = "notice_served", "Notice served – awaiting answer"
        DELIBERATION = "deliberation", "Under deliberation"
        DECIDED = "decided", "Decision issued"
        APPEALED = "appealed", "Under appeal"
        CLOSED = "closed", "Closed"
        DISMISSED = "dismissed", "Dismissed"

    case_number = models.CharField(max_length=20, unique=True, editable=False)
    title = models.CharField(max_length=200, help_text="Short description without learners' names.")
    respondents = models.ManyToManyField("students.Student", related_name="disciplinary_cases")
    summary = EncryptedTextField("Facts of the case")
    is_bullying = models.BooleanField(
        "Bullying case",
        default=False,
        help_text="Appeals go to OULLA within 10 days instead of 15.",
    )
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handled_disciplinary_cases",
    )
    protection_case = models.ForeignKey(
        "protection.ProtectionCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="disciplinary_cases",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.FILED)
    notice_served_on = models.DateField("Written notice served on", null=True, blank=True)
    answer_received_on = models.DateField(null=True, blank=True)
    answer_summary = EncryptedTextField("Respondent's answer", blank=True)
    decision_date = models.DateField(null=True, blank=True)
    decision = EncryptedTextField("Written decision", blank=True)
    appeal_filed_on = models.DateField(null=True, blank=True)
    appeal_outcome = models.TextField(blank=True)
    sanctions = models.ManyToManyField(Sanction, through="SanctionApplied", blank=True)

    objects = DisciplinaryCaseQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.case_number} – {self.title}"

    def audit_repr(self) -> str:
        return self.case_number or "Disciplinary case"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = next_reference("DC")
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        return reverse("discipline:case_detail", args=[self.pk])

    @property
    def answer_due(self):
        if not self.notice_served_on:
            return None
        return self.notice_served_on + timedelta(days=settings.DUE_PROCESS_ANSWER_DAYS)

    @property
    def appeal_days(self) -> int:
        return settings.BULLYING_APPEAL_DAYS if self.is_bullying else settings.APPEAL_DAYS

    @property
    def appeal_body(self) -> str:
        if self.is_bullying:
            return "Office of the Undersecretary for Legal and Legislative Affairs"
        return "Schools Division Superintendent or Regional Director"

    @property
    def appeal_deadline(self):
        if not self.decision_date:
            return None
        return self.decision_date + timedelta(days=self.appeal_days)

    def user_can_view(self, user) -> bool:
        return user.has_cap(Cap.VIEW_DISCIPLINE)

    def user_can_edit(self, user) -> bool:
        return user.has_cap(Cap.MANAGE_DISCIPLINE)


class SanctionApplied(TimeStampedModel):
    case = models.ForeignKey(
        DisciplinaryCase, on_delete=models.CASCADE, related_name="applied_sanctions"
    )
    sanction = models.ForeignKey(Sanction, on_delete=models.PROTECT)
    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="sanctions_applied"
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-start_date", "-created_at"]
        verbose_name = "applied sanction"

    def __str__(self) -> str:
        return f"{self.sanction} – {self.student}"

    def audit_repr(self) -> str:
        return f"Sanction on {self.case.case_number}"


class ViolationQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user.has_cap(Cap.VIEW_DISCIPLINE):
            return self
        return self.filter(
            Q(reported_by=user)
            | Q(
                student__enrollments__section__adviser=user,
                student__enrollments__section__school_year__is_current=True,
            )
        ).distinct()


class ViolationRecord(TimeStampedModel):
    """One learner's breach of school rules. Serious matters escalate to a case."""

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESOLVED = "resolved", "Resolved"
        ESCALATED = "escalated", "Escalated to disciplinary case"
        DISMISSED = "dismissed", "Dismissed"

    class Confiscation(models.TextChoices):
        NONE = "", "Nothing confiscated"
        PROHIBITED_ITEM = "prohibited", "Prohibited item (Annex F slip)"
        DEVICE = "device", "Portable device (Annex J slip)"

    student = models.ForeignKey(
        "students.Student", on_delete=models.PROTECT, related_name="violations"
    )
    offense_type = models.ForeignKey(
        OffenseType, on_delete=models.PROTECT, related_name="violations"
    )
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    description = EncryptedTextField("What happened")
    witnesses = EncryptedTextField(blank=True)
    action_taken = models.TextField("Immediate action taken", blank=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reported_violations",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    parent_notified_on = models.DateField("Parent / guardian notified on", null=True, blank=True)
    confiscation = models.CharField(
        max_length=20, choices=Confiscation.choices, blank=True, default=""
    )
    confiscated_item = models.CharField(max_length=200, blank=True)
    item_returned_on = models.DateField(null=True, blank=True)
    item_returned_to = models.CharField(max_length=150, blank=True)
    disciplinary_case = models.ForeignKey(
        DisciplinaryCase,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="violations",
    )

    objects = ViolationQuerySet.as_manager()

    class Meta:
        ordering = ["-incident_date", "-created_at"]

    def __str__(self) -> str:
        return f"{self.offense_type.name} – {self.incident_date:%b %d, %Y}"

    def audit_repr(self) -> str:
        return f"Violation #{self.pk} (learner #{self.student_id})"

    def get_absolute_url(self) -> str:
        return reverse("discipline:violation_detail", args=[self.pk])

    @property
    def offense_count(self) -> int:
        """1 for the learner's first offence of this type this school year, 2 for the second…"""
        from apps.students.models import SchoolYear

        school_year = SchoolYear.for_date(self.incident_date)
        earlier = ViolationRecord.objects.filter(
            student_id=self.student_id, offense_type_id=self.offense_type_id
        ).exclude(status=self.Status.DISMISSED)
        if school_year:
            earlier = earlier.filter(
                incident_date__gte=school_year.start_date, incident_date__lte=school_year.end_date
            )
        earlier = earlier.filter(
            Q(incident_date__lt=self.incident_date)
            | Q(incident_date=self.incident_date, pk__lte=self.pk or 0)
        )
        return max(earlier.count(), 1)

    @property
    def offense_ordinal(self) -> str:
        n = self.offense_count
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n if n < 20 else n % 10, "th")
        return f"{n}{suffix} offence"

    def user_can_view(self, user) -> bool:
        return ViolationRecord.objects.visible_to(user).filter(pk=self.pk).exists()

    def user_can_edit(self, user) -> bool:
        if user.has_cap(Cap.MANAGE_DISCIPLINE):
            return True
        return self.reported_by_id == user.pk and self.status == self.Status.OPEN
