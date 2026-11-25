from django import forms

from apps.core.forms import BaseModelForm
from apps.core.roles import Cap

from .models import Enrollment, Section, Student


class StudentForm(BaseModelForm):
    fieldsets = [
        (
            "Learner",
            [
                "lrn",
                "last_name",
                "first_name",
                "middle_name",
                "suffix",
                "sex",
                "birth_date",
                "status",
            ],
        ),
        (
            "Address and contact",
            ["address", "barangay", "municipality", "province", "contact_number"],
        ),
        ("Parent / guardian", ["guardian_name", "guardian_relationship", "guardian_contact"]),
        (
            "Family background",
            [
                "father_name",
                "father_occupation",
                "mother_name",
                "mother_occupation",
                "parents_status",
                "living_with",
                "number_of_siblings",
                "birth_order",
            ],
        ),
        ("Profile", ["is_4ps_beneficiary", "is_ip_learner", "has_disability", "interests"]),
        (
            "Confidential (guidance staff only, encrypted)",
            list(Student.CONFIDENTIAL_FIELDS),
        ),
        ("Enrolment", ["section"]),
    ]

    section = forms.ModelChoiceField(
        queryset=Section.objects.none(),
        required=False,
        help_text="Section for the current school year.",
    )

    class Meta:
        model = Student
        exclude = ["created_by", "updated_by"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not (self.user and self.user.has_cap(Cap.VIEW_CONFIDENTIAL_PROFILE)):
            for name in Student.CONFIDENTIAL_FIELDS:
                self.fields.pop(name, None)
        self.fields["section"].queryset = Section.objects.filter(
            school_year__is_current=True
        ).select_related("school_year")
        if self.instance.pk and self.instance.current_section:
            self.fields["section"].initial = self.instance.current_section.pk

    def save(self, commit=True):
        student = super().save(commit=commit)
        section = self.cleaned_data.get("section")
        if commit and section:
            current = student.current_enrollment
            if current is None:
                Enrollment.objects.create(student=student, section=section)
            elif current.section_id != section.pk:
                current.section = section
                current.save()
        return student


class EnrollmentForm(BaseModelForm):
    class Meta:
        model = Enrollment
        fields = ["section", "date_enrolled", "status"]
