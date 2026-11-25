"""Report builders. Each returns a Report made of plain tables, so the same data
renders as a printable page and as an Excel workbook.

Learner-level reports are de-identified: case numbers, sex and grade only, never names.
"""

from __future__ import annotations

import datetime
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from django.utils import timezone

SEX_COLUMNS = ["Male", "Female", "Not recorded"]


@dataclass
class ReportTable:
    title: str
    headers: list[str]
    rows: list[list] = field(default_factory=list)
    note: str = ""


@dataclass
class Report:
    key: str
    title: str
    period_label: str
    tables: list[ReportTable]
    description: str = ""


@dataclass
class Period:
    start: datetime.date
    end: datetime.date
    label: str


def _sex_label(code: str) -> str:
    return {"M": "Male", "F": "Female"}.get(code or "", "Not recorded")


def _sex_row(label: str, counter: Counter) -> list:
    values = [counter.get(col, 0) for col in SEX_COLUMNS]
    return [label, *values, sum(values)]


def _with_total(rows: list[list], label: str = "Total") -> list[list]:
    if not rows:
        return rows
    totals = [sum(row[i] for row in rows) for i in range(1, len(rows[0]))]
    return [*rows, [label, *totals]]


def _yes_no(flag: bool | None) -> str:
    if flag is None:
        return "Pending"
    return "Yes" if flag else "No"


# --- Learner rights and protection --------------------------------------------------------


def _cases(period: Period):
    from apps.protection.models import ProtectionCase

    return (
        ProtectionCase.objects.filter(
            reported_at__date__gte=period.start, reported_at__date__lte=period.end
        )
        .prefetch_related(
            "concern_types", "parties__student", "referrals__agency", "risk_assessments"
        )
        .order_by("reported_at")
    )


def _victim_sexes(case) -> list[str]:
    from apps.protection.models import CaseParty

    sexes = [_sex_label(p.party_sex) for p in case.parties.all() if p.role == CaseParty.Role.VICTIM]
    return sexes or ["Not recorded"]


def lrp_case_summary(period: Period) -> Report:
    from apps.protection.models import CaseParty, ConcernCategory, ProtectionCase

    cases = list(_cases(period))
    by_category: dict[str, Counter] = defaultdict(Counter)
    by_status = Counter()
    by_flow = Counter()
    listing = []
    for case in cases:
        sexes = _victim_sexes(case)
        for category in {ct.category for ct in case.concern_types.all()} or {"other"}:
            by_category[category].update(sexes)
        by_status[case.get_status_display()] += 1
        by_flow[case.get_flow_display() or "Not classified"] += 1
        deadlines = {d.label: d for d in case.deadlines()}
        intake = deadlines["Incident Report and Intake Sheet to disciplining authority"]
        forward = deadlines["Results forwarded to SDS and RD"]
        victims = [p for p in case.parties.all() if p.role == CaseParty.Role.VICTIM]
        respondents = [p for p in case.parties.all() if p.role == CaseParty.Role.RESPONDENT]
        listing.append(
            [
                case.case_number,
                timezone.localtime(case.reported_at).strftime("%Y-%m-%d"),
                case.flow or "—",
                ", ".join(ct.name for ct in case.concern_types.all()) or "—",
                "; ".join(
                    f"{_sex_label(p.party_sex)}, {p.party_grade or 'grade n/a'}" for p in victims
                )
                or "—",
                "; ".join(p.get_person_type_display() for p in respondents) or "—",
                case.get_status_display(),
                case.get_substantiated_display() if case.substantiated else "Pending",
                ", ".join(r.agency.name for r in case.referrals.all()) or "—",
                {"met": "Yes", "missed": "No"}.get(intake.state, "Pending"),
                {"met": "Yes", "missed": "No"}.get(
                    forward.state, "Pending" if forward.applicable else "n/a"
                ),
            ]
        )
    category_rows = [
        _sex_row(label, by_category[value])
        for value, label in ConcernCategory.choices
        if by_category.get(value)
    ]
    return Report(
        key="lrp_case_summary",
        title="Learner Rights and Protection Case Summary Report",
        period_label=period.label,
        description=(
            "Case summary for the Division LRP focal person (DO 006, s. 2026). "
            "De-identified: no learner names."
        ),
        tables=[
            ReportTable(
                "A. Affected learners by concern category and sex",
                ["Concern category", *SEX_COLUMNS, "Total"],
                _with_total(category_rows),
                "A case with several concern categories is counted under each.",
            ),
            ReportTable(
                "B. Cases by type",
                ["Case type", "Cases"],
                [[label, n] for label, n in by_flow.most_common()] + [["Total cases", len(cases)]],
            ),
            ReportTable(
                "C. Cases by status",
                ["Status", "Cases"],
                [
                    [label, by_status[label]]
                    for value, label in ProtectionCase.Status.choices
                    if by_status.get(label)
                ],
            ),
            ReportTable(
                "D. Case list",
                [
                    "Case no.",
                    "Reported",
                    "Type",
                    "Concern(s)",
                    "Affected learner(s)",
                    "Respondent(s)",
                    "Status",
                    "Substantiated",
                    "Referred to",
                    "Intake ≤ 48 h",
                    "Results to SDS/RD ≤ 30 days",
                ],
                listing,
            ),
        ],
    )


def annual_bullying_report(period: Period) -> Report:
    from apps.discipline.models import ViolationRecord
    from apps.protection.models import CaseParty, ConcernCategory
    from apps.students.models import GRADE_LEVELS

    cases = [
        case
        for case in _cases(period)
        if any(ct.category == ConcernCategory.BULLYING for ct in case.concern_types.all())
    ]
    by_type: dict[str, Counter] = defaultdict(Counter)
    by_grade: dict[str, Counter] = defaultdict(Counter)
    respondents = Counter()
    statuses = Counter()
    referrals = Counter()
    for case in cases:
        victims = [p for p in case.parties.all() if p.role == CaseParty.Role.VICTIM]
        sexes = [_sex_label(p.party_sex) for p in victims] or ["Not recorded"]
        for ct in case.concern_types.all():
            if ct.category == ConcernCategory.BULLYING:
                by_type[ct.name].update(sexes)
        for p in victims or [None]:
            grade = p.party_grade if p else ""
            by_grade[grade or "Not recorded"][_sex_label(p.party_sex if p else "")] += 1
        for p in case.parties.all():
            if p.role == CaseParty.Role.RESPONDENT:
                respondents[(p.get_person_type_display(), _sex_label(p.party_sex))] += 1
        statuses[case.get_status_display()] += 1
        for referral in case.referrals.all():
            referrals[referral.agency.get_agency_type_display()] += 1

    grade_order = [label for _, label in GRADE_LEVELS] + ["Not recorded"]
    grade_rows = [_sex_row(g, by_grade[g]) for g in grade_order if by_grade.get(g)]
    respondent_types = sorted({t for t, _ in respondents})
    respondent_rows = [
        [
            t,
            *[respondents[(t, s)] for s in SEX_COLUMNS],
            sum(respondents[(t, s)] for s in SEX_COLUMNS),
        ]
        for t in respondent_types
    ]
    violations = ViolationRecord.objects.filter(
        offense_type__is_bullying=True,
        incident_date__gte=period.start,
        incident_date__lte=period.end,
    ).count()
    return Report(
        key="annual_bullying",
        title="Annual Report on Bullying Incidents",
        period_label=period.label,
        description=(
            "For submission to the Schools Division Office in the first week of the school year "
            "(DO 006, s. 2026; RA 10627). De-identified."
        ),
        tables=[
            ReportTable(
                "A. Affected learners by type of bullying and sex",
                ["Type of bullying", *SEX_COLUMNS, "Total"],
                _with_total([_sex_row(name, counter) for name, counter in sorted(by_type.items())]),
                "A learner is counted under each type of bullying reported in their case.",
            ),
            ReportTable(
                "B. Affected learners by grade level and sex",
                ["Grade level", *SEX_COLUMNS, "Total"],
                _with_total(grade_rows),
            ),
            ReportTable(
                "C. Respondents by type and sex",
                ["Respondent", *SEX_COLUMNS, "Total"],
                _with_total(respondent_rows),
            ),
            ReportTable(
                "D. Status of bullying cases",
                ["Status", "Cases"],
                [[label, n] for label, n in statuses.most_common()]
                + [["Total bullying cases", len(cases)]],
            ),
            ReportTable(
                "E. Referrals made",
                ["Agency type", "Referrals"],
                [[label, n] for label, n in referrals.most_common()] or [["None", 0]],
            ),
            ReportTable(
                "F. Related discipline records",
                ["Measure", "Count"],
                [["Bullying-related violation records", violations]],
            ),
        ],
    )


def deadline_compliance(period: Period) -> Report:
    rows = []
    tally = Counter()
    for case in _cases(period):
        cells = [case.case_number, timezone.localtime(case.reported_at).strftime("%Y-%m-%d")]
        for d in case.deadlines():
            due = timezone.localtime(d.due).strftime("%Y-%m-%d %H:%M") if d.due else "—"
            state = d.state if d.applicable else "n/a"
            cells += [
                due,
                {"met": "Met", "missed": "Missed", "overdue": "OVERDUE"}.get(
                    state, state.replace("_", " ").title()
                ),
            ]
            tally[(d.label, state)] += 1
        rows.append(cells)
    labels = [
        "Initial Risk Assessment (Annex H)",
        "Incident Report and Intake Sheet to disciplining authority",
        "Fact-finding findings to School Head",
        "Results forwarded to SDS and RD",
    ]
    summary = [
        [label, tally[(label, "met")], tally[(label, "missed")], tally[(label, "overdue")]]
        for label in labels
    ]
    return Report(
        key="deadline_compliance",
        title="LRP Case Deadline Compliance",
        period_label=period.label,
        description="Whether each DO 006, s. 2026 timeline was met. For the School Head's monitoring.",
        tables=[
            ReportTable("A. Summary", ["Deadline", "Met", "Missed", "Overdue now"], summary),
            ReportTable(
                "B. By case",
                [
                    "Case no.",
                    "Reported",
                    "Risk assessment due",
                    "Status",
                    "Intake due",
                    "Status",
                    "Findings due",
                    "Status",
                    "SDS/RD due",
                    "Status",
                ],
                rows,
            ),
        ],
    )


# --- Guidance services and discipline ----------------------------------------------------


def guidance_services_summary(period: Period) -> Report:
    from apps.counseling.models import CounselingSession
    from apps.interventions.models import InterventionPlan

    sessions = CounselingSession.objects.filter(
        session_date__gte=period.start,
        session_date__lte=period.end,
        status=CounselingSession.Status.COMPLETED,
    ).prefetch_related("students__enrollments__section__school_year")
    by_type: dict[str, Counter] = defaultdict(Counter)
    by_concern: dict[str, Counter] = defaultdict(Counter)
    learners: dict[int, tuple[str, str]] = {}
    total_sessions = 0
    for session in sessions:
        total_sessions += 1
        for student in session.students.all():
            sex = _sex_label(student.sex)
            by_type[session.get_session_type_display()][sex] += 1
            by_concern[session.get_primary_concern_display()][sex] += 1
            section = student.section_on(session.session_date)
            learners[student.pk] = (
                section.get_grade_level_display() if section else "Not recorded",
                sex,
            )

    from apps.students.models import GRADE_LEVELS

    by_grade: dict[str, Counter] = defaultdict(Counter)
    for grade, sex in learners.values():
        by_grade[grade][sex] += 1
    grade_order = [label for _, label in GRADE_LEVELS] + ["Not recorded"]

    plans = (
        InterventionPlan.objects.filter(start_date__lte=period.end)
        .exclude(end_date__lt=period.start)
        .select_related("intervention_type")
    )
    plan_counts: dict[str, Counter] = defaultdict(Counter)
    for plan in plans:
        plan_counts[plan.intervention_type.name][plan.get_status_display()] += 1
    statuses = [label for _, label in InterventionPlan.Status.choices]

    return Report(
        key="guidance_services",
        title="Guidance and Counseling Services Summary",
        period_label=period.label,
        description=f"{total_sessions} completed session(s); {len(learners)} learner(s) served.",
        tables=[
            ReportTable(
                "A. Learner-sessions by type of service and sex",
                ["Service", *SEX_COLUMNS, "Total"],
                _with_total([_sex_row(k, v) for k, v in sorted(by_type.items())]),
                "A group session counts once for each learner who attended.",
            ),
            ReportTable(
                "B. Learner-sessions by primary concern and sex",
                ["Concern", *SEX_COLUMNS, "Total"],
                _with_total([_sex_row(k, v) for k, v in sorted(by_concern.items())]),
            ),
            ReportTable(
                "C. Learners served by grade level and sex",
                ["Grade level", *SEX_COLUMNS, "Total"],
                _with_total([_sex_row(g, by_grade[g]) for g in grade_order if by_grade.get(g)]),
            ),
            ReportTable(
                "D. Interventions active in the period",
                ["Intervention", *statuses, "Total"],
                _with_total(
                    [
                        [name, *[c.get(s, 0) for s in statuses], sum(c.values())]
                        for name, c in sorted(plan_counts.items())
                    ]
                ),
            ),
        ],
    )


def discipline_summary(period: Period) -> Report:
    from apps.discipline.models import (
        DisciplinaryCase,
        OffenseLevel,
        SanctionApplied,
        ViolationRecord,
    )

    violations = (
        ViolationRecord.objects.filter(
            incident_date__gte=period.start, incident_date__lte=period.end
        )
        .exclude(status=ViolationRecord.Status.DISMISSED)
        .select_related("student", "offense_type")
    )
    by_level: dict[str, Counter] = defaultdict(Counter)
    by_offense = Counter()
    for v in violations:
        by_level[v.offense_type.get_level_display()][_sex_label(v.student.sex)] += 1
        by_offense[(v.offense_type.get_level_display(), v.offense_type.name)] += 1
    level_rows = [
        _sex_row(label, by_level[label]) for _, label in OffenseLevel.choices if by_level.get(label)
    ]

    cases = DisciplinaryCase.objects.filter(
        created_at__date__gte=period.start, created_at__date__lte=period.end
    )
    case_status = Counter(c.get_status_display() for c in cases)
    sanctions = Counter(
        s.sanction.name
        for s in SanctionApplied.objects.filter(case__in=cases).select_related("sanction")
    )
    return Report(
        key="discipline_summary",
        title="Learner Discipline Summary",
        period_label=period.label,
        description="Violation records (dismissed ones excluded) and disciplinary cases opened in the period.",
        tables=[
            ReportTable(
                "A. Violations by offence level and sex",
                ["Offence level (DO 006 Annex I)", *SEX_COLUMNS, "Total"],
                _with_total(level_rows),
            ),
            ReportTable(
                "B. Violations by offence",
                ["Level", "Offence", "Count"],
                [[lvl, name, n] for (lvl, name), n in sorted(by_offense.items())],
            ),
            ReportTable(
                "C. Disciplinary cases by status",
                ["Status", "Cases"],
                [[k, v] for k, v in case_status.most_common()] + [["Total", cases.count()]],
            ),
            ReportTable(
                "D. Sanctions applied",
                ["Sanction", "Times applied"],
                [[k, v] for k, v in sanctions.most_common()] or [["None", 0]],
            ),
        ],
    )


REPORTS = {
    "lrp_case_summary": lrp_case_summary,
    "annual_bullying": annual_bullying_report,
    "deadline_compliance": deadline_compliance,
    "guidance_services": guidance_services_summary,
    "discipline_summary": discipline_summary,
}
