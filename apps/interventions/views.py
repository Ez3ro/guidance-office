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
    is_htmx,
)
from apps.core.permissions import ensure, require_cap
from apps.core.roles import Cap

from .forms import InterventionPlanForm, ProgressNoteForm
from .models import InterventionPlan, InterventionType


class PlanListView(GenericListView):
    model = InterventionPlan
    title = "Interventions"
    subtitle = "Intervention plans, parent conferences, behaviour contracts and outcomes."
    columns = [
        ("Title", "title"),
        ("Learner", "student.full_name"),
        ("Type", "intervention_type.name"),
        ("Start", "start_date"),
        ("Review date", "target_end_date"),
        ("Responsible", "responsible"),
        ("Status", "get_status_display"),
    ]
    search_fields = ["title", "student__last_name", "student__first_name", "student__lrn"]
    create_url_name = "interventions:create"
    create_label = "Plan intervention"
    create_caps = (Cap.MANAGE_INTERVENTIONS,)

    def get_filters(self):
        return [
            ListFilter(
                "status", "Status", InterventionPlan.Status.choices, all_label="All statuses"
            ),
            ListFilter(
                "type",
                "Type",
                list(InterventionType.objects.values_list("pk", "name")),
                lookup="intervention_type",
            ),
        ]

    def get_queryset(self):
        return super().get_queryset().select_related("student", "intervention_type", "responsible")


class PlanCreateView(GenericCreateView):
    model = InterventionPlan
    form_class = InterventionPlanForm
    required_caps = (Cap.MANAGE_INTERVENTIONS,)
    title = "Plan an intervention"
    success_message = "Intervention plan saved."

    def get_initial(self):
        initial = super().get_initial()
        for key in ("student", "violation", "disciplinary_case", "protection_case"):
            value = self.request.GET.get(key)
            if value and value.isdigit():
                initial[key] = value
        return initial

    def get_cancel_url(self):
        return reverse("interventions:list")


class PlanDetailView(GenericDetailView):
    model = InterventionPlan
    template_name = "interventions/plan_detail.html"

    def get_detail_sections(self):
        p = self.object
        return [
            (
                "Plan",
                [
                    ("Learner", p.student),
                    ("Type", p.intervention_type),
                    ("Goals and indicators", p.goals),
                    ("Responsible", p.responsible),
                    ("Start", p.start_date),
                    ("Review date", p.target_end_date),
                    ("Ended", p.end_date),
                    ("Status", p.get_status_display()),
                ],
            ),
            ("Outcome", [("Outcome", p.get_outcome_display()), ("Notes", p.outcome_notes)]),
            (
                "Linked records",
                [
                    ("Violation", p.violation),
                    ("Disciplinary case", p.disciplinary_case),
                    (
                        "Protection case",
                        p.protection_case if self.request.user.has_cap(Cap.VIEW_LRP) else None,
                    ),
                ],
            ),
        ]

    def get_actions(self):
        if self.object.user_can_edit(self.request.user):
            return [
                Action("Edit", reverse("interventions:update", args=[self.object.pk]), "bi-pencil")
            ]
        return []

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["progress_notes"] = self.object.progress_notes.select_related("recorded_by")
        if self.object.user_can_edit(self.request.user):
            ctx["progress_form"] = ProgressNoteForm(user=self.request.user)
        return ctx


class PlanUpdateView(GenericUpdateView):
    model = InterventionPlan
    form_class = InterventionPlanForm
    title = "Edit intervention plan"
    success_message = "Intervention plan updated."


@require_cap()
@require_POST
def add_progress_note(request, pk: int):
    plan = get_object_or_404(InterventionPlan, pk=pk)
    ensure(plan.user_can_edit(request.user))
    form = ProgressNoteForm(request.POST, user=request.user)
    if form.is_valid():
        note = form.save(commit=False)
        note.plan = plan
        note.recorded_by = request.user
        note.save()
        if plan.status == InterventionPlan.Status.PLANNED:
            plan.status = InterventionPlan.Status.ONGOING
            plan.save()
        form = ProgressNoteForm(user=request.user)
    if is_htmx(request):
        return render(
            request,
            "interventions/plan_detail.html#progress",
            {
                "object": plan,
                "progress_notes": plan.progress_notes.select_related("recorded_by"),
                "progress_form": form,
            },
        )
    if form.errors:
        messages.error(request, "Write a note before saving.")
    return redirect(plan.get_absolute_url() + "#progress")
