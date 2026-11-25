from django.shortcuts import get_object_or_404, render
from django.urls import reverse

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

from .forms import StudentForm
from .models import GRADE_LEVELS, Section, Student
from .timeline import KINDS, build_timeline, visible_kinds


class StudentListView(GenericListView):
    model = Student
    title = "Learners"
    columns = [
        ("Name", "full_name"),
        ("LRN", "lrn"),
        ("Sex", "get_sex_display"),
        ("Grade & section", "grade_section"),
        ("Status", "get_status_display"),
    ]
    search_fields = ["last_name", "first_name", "middle_name", "lrn"]
    search_placeholder = "Search by name or LRN…"
    create_url_name = "students:create"
    create_label = "Add learner"
    create_caps = (Cap.EDIT_STUDENTS,)
    empty_message = "No learners found."

    def get_filters(self):
        return [
            ListFilter("grade", "Grade (this S.Y.)", GRADE_LEVELS),
            ListFilter("status", "Status", Student.Status.choices),
        ]

    def apply_filter(self, qs, flt, value):
        if flt.param == "grade":
            # one filter() call so both conditions apply to the same enrolment
            return qs.filter(
                enrollments__section__grade_level=value,
                enrollments__section__school_year__is_current=True,
            ).distinct()
        return super().apply_filter(qs, flt, value)

    def get_queryset(self):
        return super().get_queryset().prefetch_related("enrollments__section__school_year")


class StudentDetailView(GenericDetailView):
    model = Student
    template_name = "students/student_detail.html"

    def get_actions(self):
        user = self.request.user
        s = self.object
        actions = []
        if s.user_can_edit(user):
            actions.append(
                Action("Edit profile", reverse("students:update", args=[s.pk]), "bi-pencil")
            )
        if user.has_cap(Cap.COUNSELING):
            actions.append(
                Action(
                    "New session",
                    reverse("counseling:create") + f"?student={s.pk}",
                    "bi-chat-heart",
                )
            )
        if user.has_cap(Cap.REPORT_INCIDENT):
            actions.append(
                Action(
                    "Log violation",
                    reverse("discipline:violation_create") + f"?student={s.pk}",
                    "bi-exclamation-triangle",
                )
            )
        if user.has_cap(Cap.MANAGE_INTERVENTIONS):
            actions.append(
                Action(
                    "Plan intervention",
                    reverse("interventions:create") + f"?student={s.pk}",
                    "bi-life-preserver",
                )
            )
        if user.has_cap(Cap.REPORT_CONCERN):
            actions.append(
                Action(
                    "Report a concern",
                    reverse("protection:report") + f"?student={s.pk}",
                    "bi-shield-exclamation",
                    "outline-danger",
                )
            )
        return actions

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.request.user
        ctx["show_confidential"] = user.has_cap(Cap.VIEW_CONFIDENTIAL_PROFILE)
        ctx["timeline"] = build_timeline(self.object, user)
        ctx["timeline_kinds"] = visible_kinds(self.object, user)
        ctx["selected_kind"] = ""
        return ctx


@require_cap()
def student_timeline(request, pk: int):
    student = get_object_or_404(Student, pk=pk)
    ensure(student.user_can_view(request.user))
    kind = request.GET.get("kind", "")
    kinds = {kind} if kind in KINDS else None
    ctx = {
        "student": student,
        "timeline": build_timeline(student, request.user, kinds),
        "timeline_kinds": visible_kinds(student, request.user),
        "selected_kind": kind,
    }
    template = (
        "students/student_detail.html#timeline"
        if is_htmx(request)
        else "students/timeline_page.html"
    )
    return render(request, template, ctx)


class StudentCreateView(GenericCreateView):
    model = Student
    form_class = StudentForm
    required_caps = (Cap.EDIT_STUDENTS,)
    title = "Add learner"
    success_message = "Learner added."

    def get_cancel_url(self):
        return reverse("students:list")


class StudentUpdateView(GenericUpdateView):
    model = Student
    form_class = StudentForm
    required_caps = (Cap.EDIT_STUDENTS,)
    title = "Edit learner profile"
    success_message = "Profile updated."


class SectionListView(GenericListView):
    model = Section
    required_caps = (Cap.VIEW_ALL_STUDENTS,)
    title = "Sections"
    columns = [
        ("Section", "short_label"),
        ("School year", "school_year.name"),
        ("Adviser", "adviser"),
        ("Learners", "enrollments.count"),
    ]
    search_fields = ["name", "adviser__last_name", "adviser__first_name"]

    def get_filters(self):
        return [ListFilter("grade_level", "Grade", GRADE_LEVELS)]

    def get_queryset(self):
        return super().get_queryset().select_related("school_year", "adviser")
