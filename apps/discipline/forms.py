from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.core.roles import Cap
from apps.students.models import Student

from .models import DisciplinaryCase, OffenseType, SanctionApplied, ViolationRecord


class ViolationForm(BaseModelForm):
    fieldsets = [
        ("Incident", ["student", "offense_type", "incident_date", "incident_time", "location"]),
        ("Details", ["description", "witnesses", "action_taken", "parent_notified_on"]),
        (
            "Confiscation",
            ["confiscation", "confiscated_item", "item_returned_on", "item_returned_to"],
        ),
        ("Case handling", ["status", "disciplinary_case"]),
    ]

    class Meta:
        model = ViolationRecord
        fields = [
            "student",
            "offense_type",
            "incident_date",
            "incident_time",
            "location",
            "description",
            "witnesses",
            "action_taken",
            "parent_notified_on",
            "confiscation",
            "confiscated_item",
            "item_returned_on",
            "item_returned_to",
            "status",
            "disciplinary_case",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Anyone who can report an incident may name any active learner.
        self.fields["student"].queryset = Student.objects.active()
        self.fields["offense_type"].queryset = OffenseType.objects.filter(is_active=True)
        if not (self.user and self.user.has_cap(Cap.MANAGE_DISCIPLINE)):
            self.fields.pop("status")
            self.fields.pop("disciplinary_case")
        else:
            self.fields["disciplinary_case"].queryset = DisciplinaryCase.objects.open()

    def clean(self):
        data = super().clean()
        if data.get("confiscation") and not data.get("confiscated_item"):
            self.add_error("confiscated_item", "Describe what was confiscated.")
        return data


class DisciplinaryCaseForm(BaseModelForm):
    fieldsets = [
        (
            "Case",
            [
                "title",
                "respondents",
                "is_bullying",
                "summary",
                "handled_by",
                "protection_case",
                "status",
            ],
        ),
        (
            "Due process (DO 006, s. 2026)",
            ["notice_served_on", "answer_received_on", "answer_summary"],
        ),
        ("Decision and appeal", ["decision_date", "decision", "appeal_filed_on", "appeal_outcome"]),
    ]

    class Meta:
        model = DisciplinaryCase
        fields = [
            "title",
            "respondents",
            "is_bullying",
            "summary",
            "handled_by",
            "protection_case",
            "status",
            "notice_served_on",
            "answer_received_on",
            "answer_summary",
            "decision_date",
            "decision",
            "appeal_filed_on",
            "appeal_outcome",
        ]
        widgets = {"respondents": forms.SelectMultiple(attrs={"size": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["respondents"].queryset = Student.objects.all()
        self.fields["handled_by"].queryset = get_user_model().objects.filter(is_active=True)
        if self.user and self.user.has_cap(Cap.VIEW_LRP):
            from apps.protection.models import ProtectionCase

            self.fields["protection_case"].queryset = ProtectionCase.objects.visible_to(self.user)
        else:
            self.fields.pop("protection_case")

    def clean(self):
        data = super().clean()
        notice, answer = data.get("notice_served_on"), data.get("answer_received_on")
        decision = data.get("decision_date")
        if answer and not notice:
            self.add_error("answer_received_on", "Record when the written notice was served first.")
        if notice and answer and answer < notice:
            self.add_error("answer_received_on", "The answer can't come before the notice.")
        if decision and notice and decision < notice:
            self.add_error("decision_date", "The decision can't come before the notice.")
        if decision and not data.get("decision"):
            self.add_error("decision", "Record the written decision.")
        return data


class SanctionAppliedForm(BaseModelForm):
    class Meta:
        model = SanctionApplied
        fields = ["student", "sanction", "start_date", "end_date", "notes"]

    def __init__(self, *args, case=None, **kwargs):
        super().__init__(*args, **kwargs)
        if case is not None:
            self.fields["student"].queryset = case.respondents.all()
        self.fields["sanction"].queryset = self.fields["sanction"].queryset.filter(is_active=True)
