from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.crud import (
    Action,
    GenericCreateView,
    GenericDetailView,
    GenericListView,
    GenericUpdateView,
    ListFilter,
)
from apps.core.permissions import ensure, require_cap
from apps.core.roles import Cap

from .forms import DisciplinaryCaseForm, SanctionAppliedForm, ViolationForm
from .models import DisciplinaryCase, OffenseLevel, ViolationRecord


class ViolationListView(GenericListView):
    model = ViolationRecord
    title = "Violation records"
    required_caps = (Cap.VIEW_DISCIPLINE, Cap.REPORT_INCIDENT)
    columns = [
        ("Date", "incident_date"),
        ("Learner", "student.full_name"),
        ("Offence", "offense_type.name"),
        ("Level", "offense_type.get_level_display"),
        ("Status", "get_status_display"),
        ("Reported by", "reported_by"),
    ]
    search_fields = [
        "student__last_name",
        "student__first_name",
        "student__lrn",
        "offense_type__name",
    ]
    search_placeholder = "Search learner, LRN or offence…"
    create_url_name = "discipline:violation_create"
    create_label = "Log violation"
    create_caps = (Cap.REPORT_INCIDENT,)

    def get_filters(self):
        return [
            ListFilter("level", "Level", OffenseLevel.choices, lookup="offense_type__level"),
            ListFilter("status", "Status", ViolationRecord.Status.choices),
        ]

    def get_queryset(self):
        return super().get_queryset().select_related("student", "offense_type", "reported_by")


class ViolationCreateView(GenericCreateView):
    model = ViolationRecord
    form_class = ViolationForm
    required_caps = (Cap.REPORT_INCIDENT,)
    title = "Log a violation"
    intro = "Record facts, not conclusions. Leave the narrative to what was seen and heard."
    success_message = "Violation recorded."

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("student"):
            initial["student"] = self.request.GET["student"]
        return initial

    def form_valid(self, form):
        form.instance.reported_by = self.request.user
        return super().form_valid(form)

    def get_cancel_url(self):
        return reverse("discipline:violations")


class ViolationDetailView(GenericDetailView):
    model = ViolationRecord
    required_caps = (Cap.VIEW_DISCIPLINE, Cap.REPORT_INCIDENT)
    template_name = "discipline/violation_detail.html"

    def get_detail_sections(self):
        v = self.object
        return [
            (
                "Incident",
                [
                    ("Learner", v.student),
                    ("Grade & section", v.student.section_on(v.incident_date) or "—"),
                    ("Offence", v.offense_type.name),
                    ("Level", v.offense_type.get_level_display()),
                    ("Offence count (this S.Y.)", v.offense_ordinal),
                    ("Date", v.incident_date),
                    ("Time", v.incident_time),
                    ("Location", v.location),
                    ("Reported by", v.reported_by),
                ],
            ),
            (
                "Details",
                [
                    ("What happened", v.description),
                    ("Witnesses", v.witnesses),
                    ("Immediate action taken", v.action_taken),
                    ("Parent / guardian notified on", v.parent_notified_on),
                    ("Status", v.get_status_display()),
                    ("Disciplinary case", v.disciplinary_case),
                ],
            ),
            (
                "Confiscation",
                [
                    ("Type", v.get_confiscation_display()),
                    ("Item", v.confiscated_item),
                    ("Returned on", v.item_returned_on),
                    ("Returned to", v.item_returned_to),
                ],
            ),
        ]

    def get_actions(self):
        v, user = self.object, self.request.user
        actions = []
        if v.user_can_edit(user):
            actions.append(
                Action("Edit", reverse("discipline:violation_update", args=[v.pk]), "bi-pencil")
            )
        if user.has_cap(Cap.MANAGE_DISCIPLINE) and not v.disciplinary_case_id:
            actions.append(
                Action(
                    "Escalate to case",
                    reverse("discipline:case_create") + f"?violation={v.pk}",
                    "bi-arrow-up-right-square",
                )
            )
        actions.append(
            Action(
                "Call slip (Annex K)",
                reverse("reports:call_slip_violation", args=[v.pk]),
                "bi-printer",
            )
        )
        if v.confiscation:
            actions.append(
                Action(
                    "Confiscation slip",
                    reverse("reports:confiscation_slip", args=[v.pk]),
                    "bi-printer",
                )
            )
        return actions


class ViolationUpdateView(GenericUpdateView):
    model = ViolationRecord
    form_class = ViolationForm
    required_caps = (Cap.MANAGE_DISCIPLINE, Cap.REPORT_INCIDENT)
    title = "Edit violation record"
    success_message = "Violation updated."


class CaseListView(GenericListView):
    model = DisciplinaryCase
    required_caps = (Cap.VIEW_DISCIPLINE,)
    title = "Disciplinary cases"
    columns = [
        ("Case no.", "case_number"),
        ("Title", "title"),
        ("Respondents", "respondents"),
        ("Status", "get_status_display"),
        ("Answer due", "answer_due"),
        ("Handled by", "handled_by"),
    ]
    search_fields = ["case_number", "title", "respondents__last_name", "respondents__first_name"]
    create_url_name = "discipline:case_create"
    create_label = "New case"
    create_caps = (Cap.MANAGE_DISCIPLINE,)

    def get_filters(self):
        return [ListFilter("status", "Status", DisciplinaryCase.Status.choices)]

    def get_queryset(self):
        return super().get_queryset().select_related("handled_by").prefetch_related("respondents")


class CaseCreateView(GenericCreateView):
    model = DisciplinaryCase
    form_class = DisciplinaryCaseForm
    required_caps = (Cap.MANAGE_DISCIPLINE,)
    title = "New disciplinary case"
    intro = (
        "Open a case when a penalty may follow. The system tracks the 10-day answer "
        "period and the appeal period from the dates you record."
    )
    success_message = "Case opened."

    def _violation(self):
        pk = self.request.GET.get("violation")
        if pk and pk.isdigit():
            return ViolationRecord.objects.filter(pk=pk).select_related("offense_type").first()
        return None

    def get_initial(self):
        initial = super().get_initial()
        initial["handled_by"] = self.request.user
        protection_case = self.request.GET.get("protection_case", "")
        if protection_case.isdigit() and self.request.user.has_cap(Cap.VIEW_LRP):
            from apps.protection.models import ProtectionCase

            linked = (
                ProtectionCase.objects.visible_to(self.request.user)
                .filter(pk=protection_case)
                .first()
            )
            if linked:
                initial["protection_case"] = linked.pk
                initial["is_bullying"] = linked.is_bullying
        violation = self._violation()
        if violation:
            initial["respondents"] = [violation.student_id]
            initial["title"] = violation.offense_type.name
            initial["is_bullying"] = violation.offense_type.is_bullying
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        violation = self._violation()
        if violation and not violation.disciplinary_case_id:
            violation.disciplinary_case = self.object
            violation.status = ViolationRecord.Status.ESCALATED
            violation.save()
        return response

    def get_cancel_url(self):
        return reverse("discipline:cases")


class CaseDetailView(GenericDetailView):
    model = DisciplinaryCase
    required_caps = (Cap.VIEW_DISCIPLINE,)
    template_name = "discipline/case_detail.html"

    def get_actions(self):
        case, user = self.object, self.request.user
        actions = []
        if case.user_can_edit(user):
            actions.append(
                Action(
                    "Edit / record due process",
                    reverse("discipline:case_update", args=[case.pk]),
                    "bi-pencil",
                )
            )
        actions.append(
            Action(
                "Call slip (Annex K)",
                reverse("reports:call_slip_case", args=[case.pk]),
                "bi-printer",
            )
        )
        return actions

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case = self.object
        ctx["violations"] = case.violations.select_related("student", "offense_type")
        ctx["applied_sanctions"] = case.applied_sanctions.select_related("sanction", "student")
        if case.user_can_edit(self.request.user):
            ctx["sanction_form"] = SanctionAppliedForm(case=case, user=self.request.user)
        return ctx


class CaseUpdateView(GenericUpdateView):
    model = DisciplinaryCase
    form_class = DisciplinaryCaseForm
    required_caps = (Cap.MANAGE_DISCIPLINE,)
    title = "Edit disciplinary case"
    success_message = "Case updated."


@require_cap(Cap.MANAGE_DISCIPLINE)
@require_POST
def add_sanction(request, pk: int):
    case = get_object_or_404(DisciplinaryCase, pk=pk)
    ensure(case.user_can_edit(request.user))
    form = SanctionAppliedForm(request.POST, case=case, user=request.user)
    if form.is_valid():
        applied = form.save(commit=False)
        applied.case = case
        applied.save()
        messages.success(request, "Sanction recorded.")
    else:
        messages.error(
            request,
            "Check the sanction details: "
            + "; ".join(f"{field}: {', '.join(errors)}" for field, errors in form.errors.items()),
        )
    return redirect(case.get_absolute_url() + "#sanctions")
