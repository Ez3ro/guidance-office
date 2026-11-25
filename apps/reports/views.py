from __future__ import annotations

import datetime

from django import forms
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import log_event
from apps.core.forms import BaseForm
from apps.core.models import SchoolProfile
from apps.core.permissions import ensure, require_cap
from apps.core.roles import Cap
from apps.students.models import SchoolYear, Student

from .services import REPORTS, Period
from .xlsx import report_to_xlsx

REPORT_CATALOGUE = [
    {
        "key": "lrp_case_summary",
        "title": "LRP Case Summary Report",
        "audience": "Division LRP focal person",
        "basis": "DO 006, s. 2026",
        "cap": Cap.VIEW_LRP,
    },
    {
        "key": "annual_bullying",
        "title": "Annual Report on Bullying Incidents",
        "audience": "Schools Division Office, first week of the school year",
        "basis": "DO 006, s. 2026; RA 10627",
        "cap": Cap.VIEW_LRP,
    },
    {
        "key": "deadline_compliance",
        "title": "LRP Case Deadline Compliance",
        "audience": "School Head (monitoring)",
        "basis": "DO 006, s. 2026 timelines",
        "cap": Cap.VIEW_LRP,
    },
    {
        "key": "guidance_services",
        "title": "Guidance and Counseling Services Summary",
        "audience": "School Head / guidance office",
        "basis": "Sex-disaggregated service statistics",
        "cap": Cap.VIEW_REPORTS,
    },
    {
        "key": "discipline_summary",
        "title": "Learner Discipline Summary",
        "audience": "School Head / Learner Formation Officer",
        "basis": "DO 006, s. 2026 offence levels",
        "cap": Cap.VIEW_DISCIPLINE,
    },
]


class PeriodForm(BaseForm):
    school_year = forms.ModelChoiceField(
        queryset=SchoolYear.objects.all(), required=False, empty_label="Custom dates…"
    )
    start = forms.DateField(required=False, widget=forms.DateInput())
    end = forms.DateField(required=False, widget=forms.DateInput())

    def period(self) -> Period:
        data = self.cleaned_data if self.is_bound and self.is_valid() else {}
        sy = data.get("school_year")
        if sy:
            return Period(
                sy.start_date,
                sy.end_date,
                f"S.Y. {sy.name} ({sy.start_date:%b %d, %Y} – {sy.end_date:%b %d, %Y})",
            )
        start, end = data.get("start"), data.get("end")
        if start and end and start <= end:
            return Period(start, end, f"{start:%b %d, %Y} – {end:%b %d, %Y}")
        current = SchoolYear.current()
        if current:
            return Period(current.start_date, current.end_date, f"S.Y. {current.name}")
        today = timezone.localdate()
        start = datetime.date(today.year, 1, 1)
        return Period(start, today, f"{start:%b %d, %Y} – {today:%b %d, %Y}")


def _entry(key: str) -> dict:
    for item in REPORT_CATALOGUE:
        if item["key"] == key:
            return item
    raise Http404


@require_cap(Cap.VIEW_REPORTS, Cap.VIEW_LRP, Cap.VIEW_DISCIPLINE)
def report_index(request):
    available = [r for r in REPORT_CATALOGUE if request.user.has_cap(r["cap"])]
    return render(request, "reports/index.html", {"reports": available})


@require_cap(Cap.VIEW_REPORTS, Cap.VIEW_LRP, Cap.VIEW_DISCIPLINE)
def report_view(request, key: str):
    entry = _entry(key)
    ensure(request.user.has_cap(entry["cap"]))
    form = PeriodForm(request.GET or None, user=request.user)
    period = form.period()
    report = REPORTS[key](period)
    school = SchoolProfile.load()
    if request.GET.get("format") == "xlsx":
        log_event(AuditEvent.Action.EXPORT, object_repr=f"{report.title} ({period.label}) – Excel")
        response = HttpResponse(
            report_to_xlsx(report, school),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = (
            f'attachment; filename="{key}-{period.start:%Y%m%d}-{period.end:%Y%m%d}.xlsx"'
        )
        return response
    log_event(AuditEvent.Action.VIEW, object_repr=f"{report.title} ({period.label})")
    return render(
        request,
        "reports/report.html",
        {"report": report, "form": form, "entry": entry, "query": request.GET.urlencode()},
    )


# --- Printable forms ----------------------------------------------------------------------


def _print(request, template: str, ctx: dict, description: str, obj=None):
    log_event(AuditEvent.Action.PRINT, obj=obj, object_repr=description)
    ctx.setdefault("printed_at", timezone.localtime())
    return render(request, template, ctx)


@require_cap(Cap.VIEW_LRP)
def intake_sheet(request, pk: int):
    from apps.protection.models import ProtectionCase

    case = get_object_or_404(ProtectionCase, pk=pk)
    ensure(case.user_has_full_access(request.user))
    return _print(
        request,
        "printable/intake_sheet.html",
        {
            "case": case,
            "parties": case.parties.select_related("student"),
            "assessment": case.risk_assessments.order_by("-assessed_at").first(),
        },
        f"Incident Report and Intake Sheet {case.case_number}",
        case,
    )


@require_cap(Cap.VIEW_LRP)
def risk_assessment_form(request, pk: int, assessment_pk: int):
    from apps.protection.models import ProtectionCase, RiskAssessment

    case = get_object_or_404(ProtectionCase, pk=pk)
    ensure(case.user_has_full_access(request.user))
    assessment = get_object_or_404(RiskAssessment, pk=assessment_pk, case=case)
    return _print(
        request,
        "printable/risk_assessment.html",
        {"case": case, "assessment": assessment},
        f"Initial Risk Assessment (Annex H) {case.case_number}",
        assessment,
    )


@require_cap(Cap.VIEW_LRP)
def fact_finding_report(request, pk: int):
    from apps.protection.models import ProtectionCase

    case = get_object_or_404(ProtectionCase, pk=pk)
    ensure(case.user_has_full_access(request.user))
    return _print(
        request,
        "printable/fact_finding.html",
        {"case": case, "parties": case.parties.select_related("student")},
        f"Fact-finding report {case.case_number}",
        case,
    )


def _call_slips(request, students, reference: str, obj):
    only = request.GET.get("student")
    if only and only.isdigit():
        students = [s for s in students if s.pk == int(only)]
    return _print(
        request,
        "printable/call_slip.html",
        {
            "students": students,
            "reference": reference,
            "meet_date": request.GET.get("date", ""),
            "meet_time": request.GET.get("time", ""),
        },
        f"Call slip(s) for {reference}",
        obj,
    )


@require_cap(Cap.VIEW_DISCIPLINE, Cap.REPORT_INCIDENT)
def call_slip_violation(request, pk: int):
    from apps.discipline.models import ViolationRecord

    violation = get_object_or_404(ViolationRecord.objects.select_related("student"), pk=pk)
    ensure(violation.user_can_view(request.user))
    return _call_slips(request, [violation.student], f"violation record #{violation.pk}", violation)


@require_cap(Cap.VIEW_DISCIPLINE)
def call_slip_case(request, pk: int):
    from apps.discipline.models import DisciplinaryCase

    case = get_object_or_404(DisciplinaryCase, pk=pk)
    return _call_slips(request, list(case.respondents.all()), case.case_number, case)


@require_cap(Cap.VIEW_LRP)
def call_slip_protection(request, pk: int):
    from apps.protection.models import ProtectionCase

    case = get_object_or_404(ProtectionCase, pk=pk)
    ensure(case.user_has_full_access(request.user))
    learners = [p.student for p in case.parties.select_related("student") if p.student_id]
    unique = list({s.pk: s for s in learners}.values())
    return _call_slips(request, unique, case.case_number, case)


@require_cap(Cap.VIEW_DISCIPLINE, Cap.REPORT_INCIDENT)
def confiscation_slip(request, pk: int):
    from apps.discipline.models import ViolationRecord

    violation = get_object_or_404(
        ViolationRecord.objects.select_related("student", "offense_type", "reported_by"), pk=pk
    )
    ensure(violation.user_can_view(request.user) and violation.confiscation)
    return _print(
        request,
        "printable/confiscation_slip.html",
        {
            "violation": violation,
            "student": violation.student,
            "section": violation.student.section_on(violation.incident_date),
            "is_device": violation.confiscation == violation.Confiscation.DEVICE,
        },
        f"Confiscation slip for violation #{violation.pk}",
        violation,
    )


@require_cap(Cap.VIEW_CONFIDENTIAL_PROFILE)
def guidance_profile_print(request, pk: int):
    student = get_object_or_404(Student, pk=pk)
    return _print(
        request,
        "printable/guidance_profile.html",
        {"student": student, "section": student.current_section},
        f"Guidance profile of learner #{student.pk}",
        student,
    )
