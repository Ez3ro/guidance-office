from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from apps.core.fields import EncryptedTextField
from apps.core.models import TimeStampedModel
from apps.core.roles import Cap

GRADE_LEVELS = [("K", "Kindergarten")] + [(str(i), f"Grade {i}") for i in range(1, 13)]
GRADE_LABELS = dict(GRADE_LEVELS)


class Sex(models.TextChoices):
    MALE = "M", "Male"
    FEMALE = "F", "Female"


class SchoolYear(models.Model):
    name = models.CharField(max_length=9, unique=True, help_text="e.g. 2026-2027")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-start_date"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_current"], condition=Q(is_current=True), name="one_current_school_year"
            )
        ]

    def __str__(self) -> str:
        return f"S.Y. {self.name}"

    def clean(self):
        if self.start_date and self.end_date and self.end_date <= self.start_date:
            raise ValidationError("The school year must end after it starts.")

    @classmethod
    def current(cls) -> SchoolYear | None:
        return cls.objects.filter(is_current=True).first()

    @classmethod
    def for_date(cls, day) -> SchoolYear | None:
        return cls.objects.filter(start_date__lte=day, end_date__gte=day).first()


class Section(models.Model):
    school_year = models.ForeignKey(SchoolYear, on_delete=models.PROTECT, related_name="sections")
    grade_level = models.CharField(max_length=2, choices=GRADE_LEVELS)
    name = models.CharField(max_length=80)
    adviser = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="advisory_sections",
    )

    class Meta:
        ordering = ["-school_year__start_date", "grade_level", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["school_year", "grade_level", "name"], name="unique_section_per_year"
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_grade_level_display()} – {self.name} ({self.school_year.name})"

    @property
    def short_label(self) -> str:
        return f"{self.get_grade_level_display()} – {self.name}"


class StudentQuerySet(models.QuerySet):
    def visible_to(self, user):
        if user.has_cap(Cap.VIEW_ALL_STUDENTS):
            return self
        return self.filter(
            enrollments__section__adviser=user,
            enrollments__section__school_year__is_current=True,
        ).distinct()

    def active(self):
        return self.filter(status=Student.Status.ACTIVE)


class Student(TimeStampedModel):
    """A learner's guidance profile."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRANSFERRED_OUT = "transferred_out", "Transferred out"
        GRADUATED = "graduated", "Graduated / completed"
        DROPPED = "dropped", "No longer attending"

    class ParentsStatus(models.TextChoices):
        MARRIED = "married", "Married, living together"
        LIVING_IN = "living_in", "Living together, not married"
        SEPARATED = "separated", "Separated"
        WIDOWED = "widowed", "Widowed"
        SOLO_PARENT = "solo_parent", "Solo parent"
        ABROAD = "abroad", "One or both working abroad (OFW)"
        OTHER = "other", "Other"

    class LivingWith(models.TextChoices):
        BOTH = "both", "Both parents"
        MOTHER = "mother", "Mother"
        FATHER = "father", "Father"
        GRANDPARENTS = "grandparents", "Grandparent(s)"
        RELATIVES = "relatives", "Other relatives"
        GUARDIAN = "guardian", "Guardian (non-relative)"
        OTHER = "other", "Other"

    lrn = models.CharField(
        "LRN",
        max_length=12,
        unique=True,
        null=True,
        blank=True,
        validators=[RegexValidator(r"^\d{12}$", "The LRN is 12 digits.")],
        help_text="Learner Reference Number (12 digits)",
    )
    last_name = models.CharField(max_length=80)
    first_name = models.CharField(max_length=80)
    middle_name = models.CharField(max_length=80, blank=True)
    suffix = models.CharField(max_length=10, blank=True, help_text="Jr., III, etc.")
    sex = models.CharField(max_length=1, choices=Sex.choices)
    birth_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)

    # Contact
    address = models.CharField("House no. / street / purok", max_length=255, blank=True)
    barangay = models.CharField(max_length=120, blank=True)
    municipality = models.CharField("City / municipality", max_length=120, blank=True)
    province = models.CharField(max_length=120, blank=True)
    contact_number = models.CharField(max_length=40, blank=True)
    guardian_name = models.CharField("Parent / guardian", max_length=150, blank=True)
    guardian_relationship = models.CharField(max_length=60, blank=True)
    guardian_contact = models.CharField("Parent / guardian contact no.", max_length=40, blank=True)

    # Family background
    father_name = models.CharField(max_length=150, blank=True)
    father_occupation = models.CharField(max_length=120, blank=True)
    mother_name = models.CharField("Mother's maiden name", max_length=150, blank=True)
    mother_occupation = models.CharField(max_length=120, blank=True)
    parents_status = models.CharField(
        "Parents' marital status", max_length=20, choices=ParentsStatus.choices, blank=True
    )
    living_with = models.CharField(max_length=20, choices=LivingWith.choices, blank=True)
    number_of_siblings = models.PositiveSmallIntegerField(null=True, blank=True)
    birth_order = models.PositiveSmallIntegerField(null=True, blank=True)
    is_4ps_beneficiary = models.BooleanField("4Ps beneficiary", default=False)
    is_ip_learner = models.BooleanField("Indigenous Peoples (IP) learner", default=False)
    has_disability = models.BooleanField("Learner with disability", default=False)
    interests = models.TextField("Interests, talents and goals", blank=True)

    # Confidential: guidance staff only, encrypted at rest
    health_notes = EncryptedTextField("Health / special needs", blank=True)
    disability_details = EncryptedTextField(blank=True)
    family_situation = EncryptedTextField("Family situation notes", blank=True)
    guidance_notes = EncryptedTextField("Counselor's notes", blank=True)

    objects = StudentQuerySet.as_manager()

    CONFIDENTIAL_FIELDS = (
        "health_notes",
        "disability_details",
        "family_situation",
        "guidance_notes",
    )

    class Meta:
        ordering = ["last_name", "first_name", "middle_name"]
        indexes = [models.Index(fields=["last_name", "first_name"])]

    def __str__(self) -> str:
        return self.full_name

    def audit_repr(self) -> str:
        return f"Learner #{self.pk}" + (f" (LRN {self.lrn})" if self.lrn else "")

    def get_absolute_url(self) -> str:
        return reverse("students:detail", args=[self.pk])

    @property
    def full_name(self) -> str:
        """DepEd style: LAST, First Middle Suffix."""
        given = " ".join(p for p in [self.first_name, self.middle_name, self.suffix] if p)
        return f"{self.last_name.upper()}, {given}"

    @property
    def display_name(self) -> str:
        middle = f" {self.middle_name[0]}." if self.middle_name else ""
        suffix = f" {self.suffix}" if self.suffix else ""
        return f"{self.first_name}{middle} {self.last_name}{suffix}"

    @property
    def age(self) -> int | None:
        if not self.birth_date:
            return None
        today = timezone.localdate()
        years = today.year - self.birth_date.year
        if (today.month, today.day) < (self.birth_date.month, self.birth_date.day):
            years -= 1
        return years

    @property
    def current_enrollment(self) -> Enrollment | None:
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("enrollments")
        if prefetched is not None:  # list pages prefetch enrolments to avoid a query per row
            return next((e for e in prefetched if e.section.school_year.is_current), None)
        return (
            self.enrollments.select_related("section", "section__school_year")
            .filter(section__school_year__is_current=True)
            .first()
        )

    @property
    def current_section(self) -> Section | None:
        enrollment = self.current_enrollment
        return enrollment.section if enrollment else None

    @property
    def grade_section(self) -> str:
        section = self.current_section
        return section.short_label if section else "Not enrolled this S.Y."

    def section_on(self, day) -> Section | None:
        enrollment = (
            self.enrollments.select_related("section")
            .filter(
                section__school_year__start_date__lte=day, section__school_year__end_date__gte=day
            )
            .first()
        )
        return enrollment.section if enrollment else None

    def is_advised_by(self, user) -> bool:
        return self.enrollments.filter(
            section__adviser=user, section__school_year__is_current=True
        ).exists()

    def user_can_view(self, user) -> bool:
        return user.has_cap(Cap.VIEW_ALL_STUDENTS) or self.is_advised_by(user)

    def user_can_edit(self, user) -> bool:
        return user.has_cap(Cap.EDIT_STUDENTS)


class Enrollment(models.Model):
    class Status(models.TextChoices):
        ENROLLED = "enrolled", "Enrolled"
        TRANSFERRED_OUT = "transferred_out", "Transferred out"
        DROPPED = "dropped", "No longer attending"
        COMPLETED = "completed", "Completed"

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="enrollments")
    section = models.ForeignKey(Section, on_delete=models.PROTECT, related_name="enrollments")
    date_enrolled = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ENROLLED)

    class Meta:
        ordering = ["-section__school_year__start_date"]
        constraints = [
            models.UniqueConstraint(fields=["student", "section"], name="unique_enrollment")
        ]

    def __str__(self) -> str:
        return f"{self.student} – {self.section}"

    def audit_repr(self) -> str:
        return f"Enrolment of learner #{self.student_id} in section #{self.section_id}"

    def clean(self):
        if not self.student_id or not self.section_id:
            return
        clash = Enrollment.objects.filter(
            student_id=self.student_id, section__school_year_id=self.section.school_year_id
        ).exclude(pk=self.pk)
        if clash.exists():
            raise ValidationError("This learner already has a section for that school year.")
