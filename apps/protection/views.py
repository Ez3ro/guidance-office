from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
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

from .forms import (
    CasePartyForm,
    ConcernReportForm,
    ProtectionCaseForm,
    ReferralForm,
    RiskAssessmentForm,
    apply_sensitivity,
)
from .models import CaseParty, ConcernCategory, ProtectionCase, Referral


class CaseListView(GenericListView):
    model = ProtectionCase
    required_caps = (Cap.VIEW_LRP,)
    title = "Learner rights and protection cases"
    columns = [
        ("Case no.", "case_number"),
        ("Reported", "reported_at"),
        ("Concerns", "concern_types"),
        ("Case type", "get_flow_display"),
        ("Status", "get_status_display"),
        ("Restricted", "restricted"),
    ]
    search_fields = ["case_number"]
    search_placeholder = "Case number…"
    create_url_name = "protection:create"
    create_label = "New case intake"
    create_caps = (Cap.MANAGE_LRP,)

    def get_filters(self):
        return [
            ListFilter("status", "Status", ProtectionCase.Status.choices),
            ListFilter(
                "category", "Concern", ConcernCategory.choices, lookup="concern_types__category"
            ),
            ListFilter("flow", "Case type", ProtectionCase.Flow.choices),
        ]

    def get_queryset(self):
        qs = super().get_queryset().prefetch_related("concern_types")
        if self.request.GET.get("category"):
            qs = qs.distinct()
        return qs

    def get_header_actions(self):
        return [Action("Report a concern", reverse("protection:report"), "bi-megaphone")]


class CaseCreateView(GenericCreateView):
    model = ProtectionCase
    form_class = ProtectionCaseForm
    required_caps = (Cap.MANAGE_LRP,)
    title = "New case intake"
    intro = (
        "Record what was reported as received. Saving starts the DO 006 clock: "
        "the Incident Report and Intake Sheet is due to the disciplining authority within 48 hours."
    )
    success_message = "Case recorded. Complete the Initial Risk Assessment next."

    def get_initial(self):
        initial = super().get_initial()
        student = self.request.GET.get("student")
        if student and student.isdigit():
            initial["victims"] = [student]
        return initial

    def form_valid(self, form):
        response = super().form_valid(form)
        form.save_parties(self.object)
        apply_sensitivity(self.object)
        return response

    def get_cancel_url(self):
        return reverse("protection:list")


class CaseDetailView(GenericDetailView):
    model = ProtectionCase
    template_name = "protection/case_detail.html"

    def get_template_names(self):
        if not self.object.user_has_full_access(self.request.user):
            return ["protection/reporter_view.html"]
        return [self.template_name]

    def get_actions(self):
        case, user = self.object, self.request.user
        if not case.user_has_full_access(user):
            return []
        actions = []
        if case.user_can_edit(user):
            actions += [
                Action(
                    "Edit / record milestones",
                    reverse("protection:update", args=[case.pk]),
                    "bi-pencil",
                ),
                Action(
                    "Risk assessment",
                    reverse("protection:risk_create", args=[case.pk]),
                    "bi-clipboard2-pulse",
                ),
            ]
        actions += [
            Action("Intake sheet", reverse("reports:intake_sheet", args=[case.pk]), "bi-printer"),
            Action(
                "Call slip", reverse("reports:call_slip_protection", args=[case.pk]), "bi-printer"
            ),
        ]
        if case.fact_finding_started_on:
            actions.append(
                Action(
                    "Fact-finding report",
                    reverse("reports:fact_finding_report", args=[case.pk]),
                    "bi-printer",
                )
            )
        return actions

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        case = self.object
        if case.user_has_full_access(self.request.user):
            ctx.update(
                parties=case.parties.select_related("student"),
                risk_assessments=case.risk_assessments.select_related("assessed_by"),
                referrals=case.referrals.select_related("agency"),
                deadlines=case.deadlines(),
                linked_sessions=case.counseling_sessions.visible_to(self.request.user),
                linked_cases=case.disciplinary_cases.all(),
                linked_interventions=case.interventions.select_related("student"),
                can_edit=case.user_can_edit(self.request.user),
            )
            if ctx["can_edit"]:
                ctx["party_form"] = CasePartyForm(user=self.request.user)
                ctx["referral_form"] = ReferralForm(user=self.request.user)
        return ctx


class CaseUpdateView(GenericUpdateView):
    model = ProtectionCase
    form_class = ProtectionCaseForm
    required_caps = (Cap.MANAGE_LRP,)
    title = "Update case"
    success_message = "Case updated."

    def form_valid(self, form):
        response = super().form_valid(form)
        apply_sensitivity(self.object)
        return response


@require_cap(Cap.REPORT_CONCERN)
def report_concern(request):
    form = ConcernReportForm(request.POST or None, user=request.user)
    if request.method == "GET" and request.GET.get("student", "").isdigit():
        form = ConcernReportForm(initial={"learners": [request.GET["student"]]}, user=request.user)
    if request.method == "POST" and form.is_valid():
        case = form.save(request.user)
        return render(request, "protection/report_received.html", {"case": case})
    return render(
        request,
        "crud/form.html",
        {
            "form": form,
            "title": "Report a learner protection concern",
            "intro": (
                "Use this when you witness, suspect or are told about abuse, bullying, violence, "
                "exploitation, discrimination or harassment involving a learner. The report goes "
                "straight to the guidance office and the Child Protection Committee. If a learner "
                "is in immediate danger, also tell the School Head or guidance counselor in person now."
            ),
            "submit_label": "Send report",
            "cancel_url": reverse("core:dashboard"),
        },
    )


class MyReportsView(GenericListView):
    model = ProtectionCase
    required_caps = (Cap.REPORT_CONCERN,)
    title = "Concerns I've reported"
    columns = [
        ("Reference", "case_number"),
        ("Sent", "reported_at"),
        ("Status", "get_status_display"),
    ]
    empty_message = "You haven't reported any concerns."

    def get_queryset(self):
        return ProtectionCase.objects.filter(created_by=self.request.user)


def _editable_case(request, pk):
    case = get_object_or_404(ProtectionCase, pk=pk)
    ensure(case.user_can_edit(request.user))
    return case


@require_cap(Cap.MANAGE_LRP)
def risk_assessment_create(request, pk: int):
    case = _editable_case(request, pk)
    form = RiskAssessmentForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        assessment = form.save(commit=False)
        assessment.case = case
        assessment.assessed_by = request.user
        assessment.save()
        messages.success(request, "Initial Risk Assessment saved.")
        return redirect(case.get_absolute_url() + "#risk")
    return render(
        request,
        "crud/form.html",
        {
            "form": form,
            "title": f"Initial Risk Assessment (Annex H) – {case.case_number}",
            "intro": "Assess the probability and impact of further harm, the actions needed, "
            "who is responsible and by when.",
            "cancel_url": case.get_absolute_url(),
        },
    )


@require_cap(Cap.MANAGE_LRP)
@require_POST
def add_party(request, pk: int):
    case = _editable_case(request, pk)
    form = CasePartyForm(request.POST, user=request.user)
    if form.is_valid():
        party = form.save(commit=False)
        party.case = case
        party.save()
        messages.success(request, f"{party.get_role_display()} added.")
    else:
        messages.error(
            request,
            "Couldn't add that person: "
            + "; ".join(" ".join(errors) for errors in form.errors.values()),
        )
    return redirect(case.get_absolute_url() + "#parties")


@require_cap(Cap.MANAGE_LRP)
@require_POST
def remove_party(request, pk: int, party_pk: int):
    case = _editable_case(request, pk)
    get_object_or_404(CaseParty, pk=party_pk, case=case).delete()
    messages.success(request, "Removed from the case.")
    return redirect(case.get_absolute_url() + "#parties")


@require_cap(Cap.MANAGE_LRP)
@require_POST
def add_referral(request, pk: int):
    case = _editable_case(request, pk)
    form = ReferralForm(request.POST, user=request.user)
    if form.is_valid():
        referral = form.save(commit=False)
        referral.case = case
        referral.save()
        messages.success(request, "Referral recorded.")
    else:
        messages.error(request, "Choose the agency and referral date.")
    return redirect(case.get_absolute_url() + "#referrals")


@require_cap(Cap.MANAGE_LRP)
def referral_update(request, pk: int, referral_pk: int):
    case = _editable_case(request, pk)
    referral = get_object_or_404(Referral, pk=referral_pk, case=case)
    form = ReferralForm(request.POST or None, instance=referral, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Referral updated.")
        return redirect(case.get_absolute_url() + "#referrals")
    return render(
        request,
        "crud/form.html",
        {
            "form": form,
            "title": f"Referral – {case.case_number}",
            "cancel_url": case.get_absolute_url(),
        },
    )
