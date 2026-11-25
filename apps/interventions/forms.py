from django.contrib.auth import get_user_model

from apps.core.forms import BaseModelForm
from apps.core.roles import Cap
from apps.students.models import Student

from .models import InterventionPlan, InterventionProgress, InterventionType


class InterventionPlanForm(BaseModelForm):
    fieldsets = [
        ("Plan", ["student", "intervention_type", "title", "goals", "responsible"]),
        ("Schedule", ["start_date", "target_end_date", "end_date", "status"]),
        ("Outcome", ["outcome", "outcome_notes"]),
        ("Linked records", ["violation", "disciplinary_case", "protection_case"]),
    ]

    class Meta:
        model = InterventionPlan
        fields = [
            "student",
            "intervention_type",
            "title",
            "goals",
            "responsible",
            "start_date",
            "target_end_date",
            "end_date",
            "status",
            "outcome",
            "outcome_notes",
            "violation",
            "disciplinary_case",
            "protection_case",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.discipline.models import DisciplinaryCase, ViolationRecord
        from apps.protection.models import ProtectionCase

        self.fields["student"].queryset = Student.objects.all()
        self.fields["intervention_type"].queryset = InterventionType.objects.filter(is_active=True)
        self.fields["responsible"].queryset = get_user_model().objects.filter(is_active=True)
        if not self.instance.pk and self.user:
            self.fields["responsible"].initial = self.user
        self.fields["violation"].queryset = ViolationRecord.objects.visible_to(
            self.user
        ).select_related("offense_type")
        self.fields["disciplinary_case"].queryset = DisciplinaryCase.objects.visible_to(self.user)
        if self.user and self.user.has_cap(Cap.VIEW_LRP):
            self.fields["protection_case"].queryset = ProtectionCase.objects.visible_to(self.user)
        else:
            self.fields.pop("protection_case")

    def clean(self):
        data = super().clean()
        start, end = data.get("start_date"), data.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "The plan can't end before it starts.")
        return data


class ProgressNoteForm(BaseModelForm):
    class Meta:
        model = InterventionProgress
        fields = ["date", "note"]
