from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.forms import BaseModelForm
from apps.students.models import Student

from .models import CalendarEvent, FollowUp


class CalendarEventForm(BaseModelForm):
    class Meta:
        model = CalendarEvent
        fields = [
            "title",
            "event_type",
            "start",
            "end",
            "location",
            "visibility",
            "participants",
            "students",
            "description",
        ]
        widgets = {
            "start": forms.DateTimeInput(),
            "end": forms.DateTimeInput(),
            "participants": forms.SelectMultiple(attrs={"size": 6}),
            "students": forms.SelectMultiple(attrs={"size": 6}),
        }
        help_texts = {
            "title": "Keep learners' names out of titles; link learners below instead.",
            "description": "Encrypted. Visible to everyone who can see the event.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["participants"].queryset = get_user_model().objects.filter(is_active=True)
        self.fields["students"].queryset = (
            Student.objects.visible_to(self.user).active() if self.user else Student.objects.none()
        )
        self.fields["students"].required = False

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["end"] < data["start"]:
            self.add_error("end", "The event can't end before it starts.")
        return data


class FollowUpForm(BaseModelForm):
    class Meta:
        model = FollowUp
        fields = [
            "title",
            "due_at",
            "assigned_to",
            "priority",
            "module",
            "student",
            "status",
            "notes",
        ]
        widgets = {"due_at": forms.DateTimeInput()}
        help_texts = {
            "title": "Reminder emails include the title, so leave learners' names out of it.",
            "module": "Who else can see it: staff with access to that module.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(is_active=True)
        self.fields["student"].queryset = (
            Student.objects.visible_to(self.user) if self.user else Student.objects.none()
        )
        if not self.instance.pk:
            self.fields["assigned_to"].initial = self.user
            self.fields.pop("status")

    def save(self, commit=True):
        follow_up = super().save(commit=False)
        if follow_up.status == FollowUp.Status.DONE and not follow_up.completed_at:
            follow_up.completed_at = timezone.now()
            follow_up.completed_by = self.user
        if commit:
            follow_up.save()
        return follow_up
