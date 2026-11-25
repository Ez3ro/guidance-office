from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel
from apps.core.roles import Cap


class CounselingSessionQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user.has_cap(Cap.COUNSELING):
            return self.none()
        return self.filter(Q(is_restricted=False) | Q(counselor=user))


class CounselingSession(TimeStampedModel):
    """Documentation of a counseling session. Notes are encrypted and guidance-only.

    The School Head and other staff see aggregate counts in reports, never notes.
    A restricted session can only be opened by the counselor who recorded it.
    """

    class SessionType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual counseling"
        GROUP = "group", "Group counseling"
        FAMILY = "family", "Family / parent counseling"
        CRISIS = "crisis", "Crisis intervention / PFA"
        FOLLOW_UP = "follow_up", "Follow-up session"
        CONSULTATION = "consultation", "Consultation with teacher / parent"

    class Modality(models.TextChoices):
        IN_PERSON = "in_person", "In person"
        ONLINE = "online", "Online"
        PHONE = "phone", "Phone"

    class ReferralSource(models.TextChoices):
        SELF = "self", "Self-referred"
        TEACHER = "teacher", "Teacher / adviser"
        PARENT = "parent", "Parent / guardian"
        SCHOOL_HEAD = "school_head", "School head"
        LFO = "lfo", "Learner Formation Officer"
        CPC = "cpc", "Child Protection Committee"
        ROUTINE = "routine", "Routine / guidance program"
        OTHER = "other", "Other"

    class Concern(models.TextChoices):
        ACADEMIC = "academic", "Academic"
        CAREER = "career", "Career"
        PERSONAL_SOCIAL = "personal_social", "Personal-social"
        FAMILY = "family", "Family"
        WELLBEING = "wellbeing", "Mental health and well-being"
        BEHAVIOURAL = "behavioural", "Behavioural"
        LRP = "lrp", "Learner rights and protection"
        OTHER = "other", "Other"

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        NO_SHOW = "no_show", "Did not attend"
        CANCELLED = "cancelled", "Cancelled"

    students = models.ManyToManyField("students.Student", related_name="counseling_sessions")
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="counseling_sessions"
    )
    session_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveSmallIntegerField(null=True, blank=True)
    session_type = models.CharField(
        max_length=20, choices=SessionType.choices, default=SessionType.INDIVIDUAL
    )
    modality = models.CharField(max_length=20, choices=Modality.choices, default=Modality.IN_PERSON)
    referral_source = models.CharField(
        max_length=20, choices=ReferralSource.choices, default=ReferralSource.SELF
    )
    primary_concern = models.CharField(max_length=20, choices=Concern.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPLETED)
    consent_obtained = models.BooleanField("Informed consent / assent obtained", default=False)
    is_restricted = models.BooleanField(
        "Restricted record",
        default=False,
        help_text="Only you will be able to open this session. Other counselors see that a session took place.",
    )
    notes = EncryptedTextField("Session notes", blank=True)
    action_plan = EncryptedTextField("Agreements and action plan", blank=True)
    next_session_date = models.DateField(null=True, blank=True)
    protection_case = models.ForeignKey(
        "protection.ProtectionCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="counseling_sessions",
    )
    disciplinary_case = models.ForeignKey(
        "discipline.DisciplinaryCase",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="counseling_sessions",
    )

    objects = CounselingSessionQuerySet.as_manager()

    class Meta:
        ordering = ["-session_date", "-start_time"]

    def __str__(self) -> str:
        return f"{self.get_session_type_display()} on {self.session_date:%b %d, %Y}"

    def audit_repr(self) -> str:
        return f"Counseling session #{self.pk}"

    def get_absolute_url(self) -> str:
        return reverse("counseling:detail", args=[self.pk])

    def user_can_view(self, user) -> bool:
        if not user.has_cap(Cap.COUNSELING):
            return False
        return not self.is_restricted or self.counselor_id == user.pk

    def user_can_edit(self, user) -> bool:
        return self.user_can_view(user)
