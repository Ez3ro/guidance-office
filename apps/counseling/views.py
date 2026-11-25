from django.urls import reverse

from apps.core.crud import (
    Action,
    GenericCreateView,
    GenericDetailView,
    GenericListView,
    GenericUpdateView,
    ListFilter,
)
from apps.core.roles import Cap

from .forms import CounselingSessionForm
from .models import CounselingSession


class SessionListView(GenericListView):
    model = CounselingSession
    required_caps = (Cap.COUNSELING,)
    title = "Counseling sessions"
    subtitle = "Confidential sessions, action plans and crisis interventions."
    columns = [
        ("Date", "session_date"),
        ("Learner(s)", "students"),
        ("Type", "get_session_type_display"),
        ("Concern", "get_primary_concern_display"),
        ("Counselor", "counselor"),
        ("Status", "get_status_display"),
        ("Restricted", "is_restricted"),
    ]
    search_fields = ["students__last_name", "students__first_name", "students__lrn"]
    search_placeholder = "Search learner or LRN…"
    create_url_name = "counseling:create"
    create_label = "Record session"

    def get_filters(self):
        return [
            ListFilter(
                "mine",
                "Counselor",
                [("1", "My sessions")],
                lookup="counselor",
                all_label="All counselors",
            ),
            ListFilter(
                "status", "Status", CounselingSession.Status.choices, all_label="All statuses"
            ),
            ListFilter(
                "primary_concern",
                "Concern",
                CounselingSession.Concern.choices,
                all_label="All concerns",
            ),
            ListFilter(
                "session_type",
                "Type",
                CounselingSession.SessionType.choices,
                all_label="All session formats",
            ),
        ]

    def apply_filter(self, qs, flt, value):
        if flt.param == "mine":
            return qs.filter(counselor=self.request.user)
        return super().apply_filter(qs, flt, value)

    def get_queryset(self):
        return super().get_queryset().select_related("counselor").prefetch_related("students")


class SessionCreateView(GenericCreateView):
    model = CounselingSession
    form_class = CounselingSessionForm
    required_caps = (Cap.COUNSELING,)
    title = "Record a counseling session"
    intro = "Notes and the action plan are encrypted and only guidance staff can read them."
    success_message = "Session saved."

    def get_initial(self):
        initial = super().get_initial()
        student = self.request.GET.get("student")
        if student and student.isdigit():
            initial["students"] = [student]
        for key in ("protection_case", "disciplinary_case"):
            value = self.request.GET.get(key, "")
            if value.isdigit():
                initial[key] = value
        return initial

    def get_cancel_url(self):
        return reverse("counseling:list")


class SessionDetailView(GenericDetailView):
    model = CounselingSession
    required_caps = (Cap.COUNSELING,)
    template_name = "counseling/session_detail.html"

    def get_detail_sections(self):
        s = self.object
        return [
            (
                "Session",
                [
                    ("Learner(s)", s.students),
                    ("Counselor", s.counselor),
                    ("Date", s.session_date),
                    ("Start time", s.start_time),
                    ("Duration (minutes)", s.duration_minutes),
                    ("Type", s.get_session_type_display()),
                    ("Modality", s.get_modality_display()),
                    ("Referral source", s.get_referral_source_display()),
                    ("Primary concern", s.get_primary_concern_display()),
                    ("Status", s.get_status_display()),
                    ("Consent / assent obtained", s.consent_obtained),
                    ("Restricted record", s.is_restricted),
                ],
            ),
            (
                "Confidential documentation",
                [
                    ("Session notes", s.notes),
                    ("Agreements and action plan", s.action_plan),
                    ("Next session", s.next_session_date),
                ],
            ),
            (
                "Linked records",
                [
                    ("Protection case", s.protection_case),
                    ("Disciplinary case", s.disciplinary_case),
                ],
            ),
        ]

    def get_actions(self):
        if self.object.user_can_edit(self.request.user):
            return [
                Action("Edit", reverse("counseling:update", args=[self.object.pk]), "bi-pencil")
            ]
        return []


class SessionUpdateView(GenericUpdateView):
    model = CounselingSession
    form_class = CounselingSessionForm
    required_caps = (Cap.COUNSELING,)
    title = "Edit counseling session"
    success_message = "Session updated."
