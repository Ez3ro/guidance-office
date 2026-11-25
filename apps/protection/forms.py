from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Case, IntegerField, Value, When

from apps.core.forms import BaseForm, BaseModelForm
from apps.students.models import Student

from .models import (
    CaseParty,
    ConcernCategory,
    ConcernType,
    ProtectionCase,
    Referral,
    ReferralAgency,
    RiskAssessment,
)


def ordered_concerns():
    """Active concern types in the order of ConcernCategory (bullying first, other last)."""
    order = Case(
        *[
            When(category=value, then=Value(i))
            for i, (value, _) in enumerate(ConcernCategory.choices)
        ],
        output_field=IntegerField(),
    )
    return (
        ConcernType.objects.filter(is_active=True)
        .annotate(category_order=order)
        .order_by("category_order", "name")
    )


def concern_grouping():
    labels = dict(ConcernCategory.choices)
    mapping = {
        pk: labels.get(cat, cat) for pk, cat in ConcernType.objects.values_list("pk", "category")
    }
    return {"concern_types": lambda pk: mapping.get(int(pk), "Other")}


def _concern_field(**kwargs):
    return forms.ModelMultipleChoiceField(
        queryset=ConcernType.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        **kwargs,
    )


class ProtectionCaseForm(BaseModelForm):
    """Full case form for LRP staff."""

    victims = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        label="Affected learner(s)",
        widget=forms.SelectMultiple(attrs={"size": 5}),
        help_text="Enrolled learners only. Add other people on the case page.",
    )
    learner_respondents = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        label="Respondent learner(s)",
        widget=forms.SelectMultiple(attrs={"size": 5}),
        help_text="For adult respondents, add them on the case page after saving.",
    )

    fieldsets = [
        (
            "Report",
            [
                "reported_at",
                "received_by",
                "report_channel",
                "informant_name",
                "informant_relationship",
                "informant_contact",
            ],
        ),
        (
            "Incident",
            [
                "incident_date",
                "incident_time",
                "incident_location",
                "location_details",
                "narrative",
                "initial_actions",
            ],
        ),
        ("People involved", ["victims", "learner_respondents"]),
        ("Classification", ["concern_types", "flow", "restricted"]),
        (
            "DO 006 workflow",
            [
                "status",
                "substantiated",
                "disciplining_authority",
                "intake_referred_at",
                "fact_finding_started_on",
                "findings",
                "findings_submitted_on",
                "forwarded_to_sds_rd_on",
            ],
        ),
        ("Outcome", ["outcome_summary"]),
    ]

    class Meta:
        model = ProtectionCase
        fields = [
            "reported_at",
            "received_by",
            "report_channel",
            "informant_name",
            "informant_relationship",
            "informant_contact",
            "incident_date",
            "incident_time",
            "incident_location",
            "location_details",
            "narrative",
            "initial_actions",
            "concern_types",
            "flow",
            "restricted",
            "status",
            "substantiated",
            "disciplining_authority",
            "intake_referred_at",
            "fact_finding_started_on",
            "findings",
            "findings_submitted_on",
            "forwarded_to_sds_rd_on",
            "outcome_summary",
        ]
        widgets = {
            "reported_at": forms.DateTimeInput(),
            "intake_referred_at": forms.DateTimeInput(),
            "concern_types": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["concern_types"].queryset = ordered_concerns()
        self.checkbox_grouping = concern_grouping()
        self.fields["received_by"].queryset = get_user_model().objects.filter(is_active=True)
        if not self.instance.pk and self.user:
            self.fields["received_by"].initial = self.user
        if self.instance.pk:
            # parties are managed on the case page once the case exists
            self.fields.pop("victims")
            self.fields.pop("learner_respondents")
        else:
            self.fields["victims"].queryset = Student.objects.all()
            self.fields["learner_respondents"].queryset = Student.objects.all()

    def clean(self):
        data = super().clean()
        started, submitted = data.get("fact_finding_started_on"), data.get("findings_submitted_on")
        if submitted and not started:
            self.add_error("findings_submitted_on", "Record when fact-finding started first.")
        if data.get("forwarded_to_sds_rd_on") and not submitted:
            self.add_error(
                "forwarded_to_sds_rd_on", "Record when findings went to the School Head first."
            )
        if data.get("status") == ProtectionCase.Status.CLOSED and not data.get("outcome_summary"):
            self.add_error("outcome_summary", "Summarise the outcome before closing the case.")
        return data

    def save_parties(self, case: ProtectionCase) -> None:
        for student in self.cleaned_data.get("victims") or []:
            CaseParty.objects.create(case=case, role=CaseParty.Role.VICTIM, student=student)
        for student in self.cleaned_data.get("learner_respondents") or []:
            CaseParty.objects.create(case=case, role=CaseParty.Role.RESPONDENT, student=student)


class ConcernReportForm(BaseForm):
    """Short form any staff member can use to report a learner protection concern."""

    learners = forms.ModelMultipleChoiceField(
        queryset=Student.objects.none(),
        required=False,
        label="Learner(s) affected",
        widget=forms.SelectMultiple(attrs={"size": 5}),
        help_text="Leave empty if you don't know who it is.",
    )
    concern_types = _concern_field(label="What kind of concern is it?")
    incident_date = forms.DateField(required=False, widget=forms.DateInput())
    incident_location = forms.ChoiceField(choices=ProtectionCase.Location.choices)
    location_details = forms.CharField(max_length=200, required=False)
    narrative = forms.CharField(
        label="What did you see, hear or were told?",
        widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Write it down as you received it. Don't question the learner further; "
        "the guidance office and CPC will take it from here.",
    )
    immediate_danger = forms.BooleanField(
        required=False, label="I think the learner may be in immediate danger"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["learners"].queryset = Student.objects.active()
        self.fields["concern_types"].queryset = ordered_concerns()
        self.checkbox_grouping = concern_grouping()

    def save(self, user) -> ProtectionCase:
        data = self.cleaned_data
        narrative = data["narrative"]
        if data["immediate_danger"]:
            narrative = "[Reporter flagged possible immediate danger]\n\n" + narrative
        case = ProtectionCase.objects.create(
            report_channel=ProtectionCase.Channel.TEACHER,
            informant_name=user.display_name,
            informant_relationship=user.position or user.get_role_display(),
            incident_date=data["incident_date"],
            incident_location=data["incident_location"],
            location_details=data["location_details"],
            narrative=narrative,
        )
        case.concern_types.set(data["concern_types"])
        for student in data["learners"]:
            CaseParty.objects.create(case=case, role=CaseParty.Role.VICTIM, student=student)
        apply_sensitivity(case)
        return case


def apply_sensitivity(case: ProtectionCase) -> None:
    """Restricts the case automatically when a sensitive concern type was selected."""
    if not case.restricted and case.concern_types.filter(is_sensitive=True).exists():
        case.restricted = True
        case.save()


class CasePartyForm(BaseModelForm):
    class Meta:
        model = CaseParty
        fields = [
            "role",
            "person_type",
            "student",
            "full_name",
            "sex",
            "age",
            "grade_or_position",
            "relationship_to_victim",
            "notes",
        ]
        widgets = {"full_name": forms.TextInput(), "notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = Student.objects.all()

    def clean(self):
        data = super().clean()
        if (
            not data.get("student")
            and not data.get("full_name")
            and data.get("person_type") != CaseParty.PersonType.UNKNOWN
        ):
            self.add_error("full_name", "Pick an enrolled learner or type the person's name.")
        return data


class RiskAssessmentForm(BaseModelForm):
    fieldsets = [
        (
            "Assessment",
            ["assessed_at", "risk_factors", "probability", "impact", "immediate_danger"],
        ),
        (
            "Immediate needs",
            [
                "needs_medical_care",
                "needs_pfa",
                "needs_safety_plan",
                "parents_notified",
                "parents_not_notified_reason",
            ],
        ),
        ("Plan", ["actions_needed", "responsible_persons", "timeline"]),
    ]

    class Meta:
        model = RiskAssessment
        fields = [
            "assessed_at",
            "risk_factors",
            "probability",
            "impact",
            "immediate_danger",
            "needs_medical_care",
            "needs_pfa",
            "needs_safety_plan",
            "parents_notified",
            "parents_not_notified_reason",
            "actions_needed",
            "responsible_persons",
            "timeline",
        ]
        widgets = {"assessed_at": forms.DateTimeInput()}

    def clean(self):
        data = super().clean()
        if not data.get("parents_notified") and not data.get("parents_not_notified_reason"):
            self.add_error(
                "parents_not_notified_reason",
                "Say why the parents or guardians weren't notified (or tick that they were).",
            )
        return data


class ReferralForm(BaseModelForm):
    class Meta:
        model = Referral
        fields = ["agency", "referred_on", "reason", "status", "feedback"]
        widgets = {
            "reason": forms.Textarea(attrs={"rows": 2}),
            "feedback": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["agency"].queryset = ReferralAgency.objects.filter(is_active=True)
