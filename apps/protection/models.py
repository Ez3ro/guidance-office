"""Learner rights and protection (LRP) cases.

Implements the DepEd Child Protection Policy (DO 40, s. 2012) as harmonised by
DO 006, s. 2026 (Guidelines on Ensuring a Safe and Motivating Learning Environment):
risk assessment (Annex H), Incident Report and Intake Sheet within 48 hours,
fact-finding findings to the School Head within 10 calendar days, and results to
the SDS and RD within 30 calendar days of receiving the report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel, next_reference
from apps.core.roles import Cap


class ConcernCategory(models.TextChoices):
    BULLYING = "bullying", "Bullying"
    CHILD_ABUSE = "child_abuse", "Child abuse"
    VIOLENCE = "violence", "Violence"
    EXPLOITATION = "exploitation", "Exploitation"
    DISCRIMINATION = "discrimination", "Discrimination"
    GBSH = "gbsh", "Gender-based sexual harassment"
    CYBER = "cyber", "Cyber-related harm"
    CORPORAL_PUNISHMENT = "corporal", "Corporal punishment / degrading treatment"
    OTHER = "other", "Other LRP concern"


class ConcernType(models.Model):
    category = models.CharField(max_length=20, choices=ConcernCategory.choices)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    is_sensitive = models.BooleanField(
        default=False,
        help_text="Cases with this concern are restricted to the School Head and guidance staff.",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "name"]
        constraints = [
            models.UniqueConstraint(fields=["category", "name"], name="unique_concern_type")
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_bullying(self) -> bool:
        return self.category == ConcernCategory.BULLYING


class ReferralAgency(models.Model):
    class AgencyType(models.TextChoices):
        SOCIAL_WELFARE = "social_welfare", "Social welfare (DSWD / LSWDO)"
        LAW_ENFORCEMENT = "law_enforcement", "Law enforcement (PNP-WCPD, NBI)"
        BARANGAY = "barangay", "Barangay (BCPC, VAW desk)"
        HEALTH = "health", "Health / medical"
        MENTAL_HEALTH = "mental_health", "Mental health professional"
        DEPED = "deped", "DepEd office"
        LEGAL = "legal", "Legal assistance"
        OTHER = "other", "Other"

    name = models.CharField(max_length=200, unique=True)
    agency_type = models.CharField(max_length=20, choices=AgencyType.choices)
    contact_info = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "referral agencies"

    def __str__(self) -> str:
        return self.name


class ProtectionCaseQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Full case access for LRP staff; reporters only see that their report exists."""
        if user.has_cap(Cap.VIEW_RESTRICTED_LRP):
            return self
        if user.has_cap(Cap.VIEW_LRP):
            return self.filter(Q(restricted=False) | Q(created_by=user))
        return self.filter(created_by=user)

    def open(self):
        return self.exclude(
            status__in=[ProtectionCase.Status.CLOSED, ProtectionCase.Status.DISMISSED]
        )


@dataclass
class Deadline:
    label: str
    basis: str
    due: datetime | None
    done_at: datetime | date | None
    applicable: bool = True

    @property
    def state(self) -> str:
        if not self.applicable:
            return "pending"
        now = timezone.now()
        due = self.due
        if self.done_at is not None:
            done = self.done_at
            if isinstance(done, date) and not isinstance(done, datetime):
                done = timezone.make_aware(datetime.combine(done, datetime.min.time()))
            return "met" if due is None or done <= due else "missed"
        if due is not None and due < now:
            return "overdue"
        if due is not None and due < now + timedelta(days=1):
            return "due_soon"
        return "open"

    @property
    def state_label(self) -> str:
        return {
            "met": "Met",
            "missed": "Missed",
            "overdue": "Overdue",
            "due_soon": "Due soon",
            "open": "Open",
            "pending": "Pending",
        }[self.state]


class ProtectionCase(TimeStampedModel):
    class Flow(models.TextChoices):
        ADULT_TO_LEARNER = "A", "Involves school personnel or another adult (Annex A)"
        LEARNER_TO_LEARNER = "B", "Learner to learner (Annex B)"
        LEARNER_TO_COMMUNITY = "C", "Learner to community (Annex C)"

    class Status(models.TextChoices):
        REPORTED = "reported", "Reported – awaiting risk assessment"
        ASSESSED = "assessed", "Risk assessed"
        INTAKE_REFERRED = "intake_referred", "Intake referred to disciplining authority"
        FACT_FINDING = "fact_finding", "Fact-finding in progress"
        FINDINGS_SUBMITTED = "findings_submitted", "Findings submitted to School Head"
        FORWARDED = "forwarded", "Results forwarded to SDS and RD"
        RESOLVED = "resolved", "Resolved – monitoring"
        CLOSED = "closed", "Closed"
        DISMISSED = "dismissed", "Not substantiated / dismissed"

    # Order of the automatic workflow steps (manual states come after).
    STATUS_ORDER = [
        Status.REPORTED,
        Status.ASSESSED,
        Status.INTAKE_REFERRED,
        Status.FACT_FINDING,
        Status.FINDINGS_SUBMITTED,
        Status.FORWARDED,
    ]

    class Channel(models.TextChoices):
        DISCLOSURE = "disclosure", "Disclosure by the learner"
        TEACHER = "teacher", "Teacher / school personnel"
        PARENT = "parent", "Parent / guardian"
        PEER = "peer", "Another learner"
        ANONYMOUS = "anonymous", "Anonymous"
        HOTLINE = "hotline", "Hotline / phone"
        ONLINE = "online", "Online / email"
        OTHER = "other", "Other"

    class Location(models.TextChoices):
        ON_CAMPUS = "on_campus", "On campus"
        ONLINE = "online", "Online / virtual space"
        SCHOOL_ACTIVITY = "school_activity", "School activity (off-campus)"
        SCHOOL_RELATED = "school_related", "School-related, off-campus"
        OUTSIDE = "outside", "Outside school"

    class Substantiated(models.TextChoices):
        PENDING = "", "Not yet determined"
        YES = "yes", "Substantiated"
        NO = "no", "Not substantiated"

    case_number = models.CharField(max_length=20, unique=True, editable=False)
    flow = models.CharField(
        "Case type",
        max_length=1,
        choices=Flow.choices,
        blank=True,
        help_text="Which DO 006 process flow applies.",
    )
    concern_types = models.ManyToManyField(ConcernType, related_name="cases")
    reported_at = models.DateTimeField("Report received", default=timezone.now)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="received_protection_cases",
    )
    report_channel = models.CharField(
        max_length=20, choices=Channel.choices, default=Channel.TEACHER
    )
    informant_name = EncryptedTextField("Informant / complainant", blank=True)
    informant_relationship = models.CharField(
        "Informant's relationship to the learner", max_length=100, blank=True
    )
    informant_contact = EncryptedTextField(blank=True)
    incident_date = models.DateField(null=True, blank=True)
    incident_time = models.TimeField(null=True, blank=True)
    incident_location = models.CharField(
        max_length=20, choices=Location.choices, default=Location.ON_CAMPUS
    )
    location_details = models.CharField(max_length=200, blank=True)
    narrative = EncryptedTextField("What was reported")
    initial_actions = EncryptedTextField(
        "Initial interventions",
        blank=True,
        help_text="Immediate safety measures, PFA, medical care, parent notice.",
    )
    restricted = models.BooleanField(
        "Restricted case",
        default=False,
        help_text="Only the School Head and guidance staff can open it.",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REPORTED)
    substantiated = models.CharField(
        max_length=3, choices=Substantiated.choices, blank=True, default=""
    )
    disciplining_authority = models.CharField(
        max_length=150,
        blank=True,
        help_text="Name and position of the person the intake was referred to.",
    )
    intake_referred_at = models.DateTimeField(
        "Intake sheet referred to disciplining authority", null=True, blank=True
    )
    fact_finding_started_on = models.DateField(null=True, blank=True)
    findings = EncryptedTextField("Fact-finding findings", blank=True)
    findings_submitted_on = models.DateField(
        "Findings submitted to School Head", null=True, blank=True
    )
    forwarded_to_sds_rd_on = models.DateField(
        "Results forwarded to SDS and RD", null=True, blank=True
    )
    outcome_summary = EncryptedTextField("Outcome and monitoring", blank=True)
    closed_on = models.DateField(null=True, blank=True)

    objects = ProtectionCaseQuerySet.as_manager()

    class Meta:
        ordering = ["-reported_at"]
        verbose_name = "protection case"

    def __str__(self) -> str:
        return self.case_number or "New case"

    def audit_repr(self) -> str:
        return self.case_number or "Protection case"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = next_reference("CP")
        self._advance_status()
        if self.status in {self.Status.CLOSED, self.Status.DISMISSED} and not self.closed_on:
            self.closed_on = timezone.localdate()
        super().save(*args, **kwargs)

    def _advance_status(self) -> None:
        """Moves the status forward when a milestone date is recorded (never backwards)."""
        if self.status not in self.STATUS_ORDER:
            return
        reached = self.status
        if self.intake_referred_at:
            reached = self.Status.INTAKE_REFERRED
        if self.fact_finding_started_on:
            reached = self.Status.FACT_FINDING
        if self.findings_submitted_on:
            reached = self.Status.FINDINGS_SUBMITTED
        if self.forwarded_to_sds_rd_on:
            reached = self.Status.FORWARDED
        if self.STATUS_ORDER.index(reached) > self.STATUS_ORDER.index(self.status):
            self.status = reached

    def get_absolute_url(self) -> str:
        return reverse("protection:detail", args=[self.pk])

    # --- Access ---------------------------------------------------------------------------
    def user_has_full_access(self, user) -> bool:
        if user.has_cap(Cap.VIEW_RESTRICTED_LRP):
            return True
        return user.has_cap(Cap.VIEW_LRP) and not self.restricted

    def user_can_view(self, user) -> bool:
        return self.user_has_full_access(user) or self.created_by_id == user.pk

    def user_can_edit(self, user) -> bool:
        return self.user_has_full_access(user) and user.has_cap(Cap.MANAGE_LRP)

    # --- Parties and categories ---------------------------------------------------------
    @property
    def victims(self):
        return self.parties.filter(role=CaseParty.Role.VICTIM)

    @property
    def respondents(self):
        return self.parties.filter(role=CaseParty.Role.RESPONDENT)

    @property
    def is_bullying(self) -> bool:
        return self.concern_types.filter(category=ConcernCategory.BULLYING).exists()

    @property
    def is_open(self) -> bool:
        return self.status not in {self.Status.CLOSED, self.Status.DISMISSED}

    # --- DO 006 deadlines ---------------------------------------------------------------
    @property
    def risk_assessment_target(self) -> datetime:
        return self.reported_at + timedelta(hours=settings.LRP_RISK_ASSESSMENT_TARGET_HOURS)

    @property
    def intake_due_at(self) -> datetime:
        return self.reported_at + timedelta(hours=settings.LRP_INTAKE_DEADLINE_HOURS)

    @property
    def fact_finding_due(self) -> date | None:
        if not self.fact_finding_started_on:
            return None
        return self.fact_finding_started_on + timedelta(days=settings.LRP_FACT_FINDING_DAYS)

    @property
    def forward_due(self) -> date:
        return timezone.localtime(self.reported_at).date() + timedelta(
            days=settings.LRP_FORWARD_DAYS
        )

    def deadlines(self) -> list[Deadline]:
        from apps.scheduling.services import end_of_day

        first_assessment = self.risk_assessments.order_by("assessed_at").first()
        investigated = bool(self.fact_finding_started_on)
        return [
            Deadline(
                "Initial Risk Assessment (Annex H)",
                f"School target: {settings.LRP_RISK_ASSESSMENT_TARGET_HOURS} h from report",
                self.risk_assessment_target,
                first_assessment.assessed_at if first_assessment else None,
            ),
            Deadline(
                "Incident Report and Intake Sheet to disciplining authority",
                f"{settings.LRP_INTAKE_DEADLINE_HOURS} hours from report",
                self.intake_due_at,
                self.intake_referred_at,
            ),
            Deadline(
                "Fact-finding findings to School Head",
                f"{settings.LRP_FACT_FINDING_DAYS} calendar days from start of fact-finding",
                end_of_day(self.fact_finding_due) if self.fact_finding_due else None,
                self.findings_submitted_on,
                applicable=investigated,
            ),
            Deadline(
                "Results forwarded to SDS and RD",
                f"{settings.LRP_FORWARD_DAYS} calendar days from receipt of report",
                end_of_day(self.forward_due),
                self.forwarded_to_sds_rd_on,
                applicable=investigated,
            ),
        ]


class CaseParty(models.Model):
    class Role(models.TextChoices):
        VICTIM = "victim", "Victim / affected learner"
        RESPONDENT = "respondent", "Respondent"
        COMPLAINANT = "complainant", "Complainant"
        WITNESS = "witness", "Witness"

    class PersonType(models.TextChoices):
        LEARNER = "learner", "Learner"
        TEACHING = "teaching", "Teaching personnel"
        NON_TEACHING = "non_teaching", "Non-teaching personnel"
        PARENT = "parent", "Parent / guardian"
        OTHER_ADULT = "other_adult", "Other adult"
        UNKNOWN = "unknown", "Unknown / unidentified"

    case = models.ForeignKey(ProtectionCase, on_delete=models.CASCADE, related_name="parties")
    role = models.CharField(max_length=20, choices=Role.choices)
    person_type = models.CharField(
        max_length=20, choices=PersonType.choices, default=PersonType.LEARNER
    )
    student = models.ForeignKey(
        "students.Student",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="protection_parties",
        help_text="Pick the learner if they're enrolled here.",
    )
    full_name = EncryptedTextField("Name (if not an enrolled learner)", blank=True)
    sex = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")], blank=True)
    age = models.PositiveSmallIntegerField(null=True, blank=True)
    grade_or_position = models.CharField(max_length=100, blank=True)
    relationship_to_victim = models.CharField(max_length=100, blank=True)
    notes = EncryptedTextField(blank=True)

    class Meta:
        ordering = ["role", "id"]
        verbose_name = "case party"
        verbose_name_plural = "case parties"

    def __str__(self) -> str:
        return f"{self.display_name} ({self.get_role_display()})"

    def audit_repr(self) -> str:
        return f"{self.get_role_display()} on {self.case.case_number}"

    @property
    def display_name(self) -> str:
        if self.student_id:
            return self.student.full_name
        return self.full_name or "(name not recorded)"

    @property
    def party_sex(self) -> str:
        return self.student.sex if self.student_id else self.sex

    @property
    def party_grade(self) -> str:
        if self.student_id:
            section = self.student.section_on(timezone.localtime(self.case.reported_at).date())
            return section.get_grade_level_display() if section else ""
        return self.grade_or_position


class RiskAssessment(TimeStampedModel):
    """Initial Risk Assessment (DO 006, s. 2026, Annex H): probability, impact, action,
    responsible persons and timeline. Field layout to be checked against the signed annex."""

    class Level(models.IntegerChoices):
        LOW = 1, "Low"
        MEDIUM = 2, "Medium"
        HIGH = 3, "High"

    case = models.ForeignKey(
        ProtectionCase, on_delete=models.CASCADE, related_name="risk_assessments"
    )
    assessed_at = models.DateTimeField(default=timezone.now)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    risk_factors = EncryptedTextField("Risk factors identified")
    probability = models.PositiveSmallIntegerField(
        "Probability of further harm", choices=Level.choices, default=Level.MEDIUM
    )
    impact = models.PositiveSmallIntegerField(
        "Impact on the learner", choices=Level.choices, default=Level.MEDIUM
    )
    immediate_danger = models.BooleanField("Learner is in immediate danger", default=False)
    needs_medical_care = models.BooleanField(default=False)
    needs_pfa = models.BooleanField("Needs psychological first aid", default=False)
    needs_safety_plan = models.BooleanField(
        "Needs a safety plan / separation from respondent", default=False
    )
    parents_notified = models.BooleanField("Parents / guardians notified", default=False)
    parents_not_notified_reason = models.CharField(
        max_length=255, blank=True, help_text="e.g. a parent is the alleged respondent"
    )
    actions_needed = EncryptedTextField("Actions needed")
    responsible_persons = models.CharField(max_length=255)
    timeline = models.CharField("Timeline / target dates", max_length=255)

    class Meta:
        ordering = ["-assessed_at"]

    def __str__(self) -> str:
        return f"Risk assessment {self.assessed_at:%b %d, %Y}"

    def audit_repr(self) -> str:
        return f"Risk assessment on {self.case.case_number}"

    def get_absolute_url(self) -> str:
        return reverse("protection:detail", args=[self.case_id]) + "#risk"

    @property
    def score(self) -> int:
        return self.probability * self.impact

    @property
    def overall_level(self) -> str:
        if self.immediate_danger or self.score >= 9:
            return "critical"
        if self.score >= 6:
            return "high"
        if self.score >= 3:
            return "moderate"
        return "low"


class Referral(TimeStampedModel):
    class Status(models.TextChoices):
        SENT = "sent", "Referred"
        ACKNOWLEDGED = "acknowledged", "Acknowledged by agency"
        IN_PROGRESS = "in_progress", "Being handled"
        COMPLETED = "completed", "Completed"
        DECLINED = "declined", "Declined / not pursued"

    case = models.ForeignKey(ProtectionCase, on_delete=models.CASCADE, related_name="referrals")
    agency = models.ForeignKey(ReferralAgency, on_delete=models.PROTECT, related_name="referrals")
    referred_on = models.DateField(default=timezone.localdate)
    reason = EncryptedTextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SENT)
    feedback = EncryptedTextField("Agency feedback", blank=True)

    class Meta:
        ordering = ["-referred_on"]

    def __str__(self) -> str:
        return f"{self.agency} ({self.referred_on:%b %d, %Y})"

    def audit_repr(self) -> str:
        return f"Referral on {self.case.case_number}"
