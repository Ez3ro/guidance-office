from django import forms
from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.core.roles import Cap
from apps.students.models import Student

from .models import CounselingSession


class CounselingSessionForm(BaseModelForm):
    fieldsets = [
        (
            "Session",
            [
                "students",
                "counselor",
                "session_date",
                "start_time",
                "duration_minutes",
                "session_type",
                "modality",
                "referral_source",
                "primary_concern",
                "status",
            ],
        ),
        (
            "Documentation (encrypted)",
            ["consent_obtained", "notes", "action_plan", "next_session_date", "is_restricted"],
        ),
        ("Linked records", ["protection_case", "disciplinary_case"]),
    ]

    class Meta:
        model = CounselingSession
        fields = [
            "students",
            "counselor",
            "session_date",
            "start_time",
            "duration_minutes",
            "session_type",
            "modality",
            "referral_source",
            "primary_concern",
            "status",
            "consent_obtained",
            "notes",
            "action_plan",
            "next_session_date",
            "is_restricted",
            "protection_case",
            "disciplinary_case",
        ]
        widgets = {"students": forms.SelectMultiple(attrs={"size": 6})}
        help_texts = {
            "students": "Pick one learner for individual sessions, several for group sessions.",
            "notes": "Write what the counselor needs to continue care. Avoid verbatim quotes "
            "unless they matter for safety.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["students"].queryset = Student.objects.all()
        self.fields["counselor"].queryset = get_user_model().objects.filter(
            is_active=True, role__in=["counselor", "guidance_designate"]
        )
        if not self.instance.pk and self.user:
            self.fields["counselor"].initial = self.user
        from apps.discipline.models import DisciplinaryCase
        from apps.protection.models import ProtectionCase

        if self.user and self.user.has_cap(Cap.VIEW_LRP):
            self.fields["protection_case"].queryset = ProtectionCase.objects.visible_to(self.user)
        else:
            self.fields.pop("protection_case")
        self.fields["disciplinary_case"].queryset = DisciplinaryCase.objects.visible_to(self.user)

    def clean(self):
        data = super().clean()
        if data.get("is_restricted") and self.user and data.get("counselor") != self.user:
            self.add_error(
                "is_restricted",
                "Only the counselor who holds the session can restrict it.",
            )
        return data
