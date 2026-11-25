"""Case history and disciplinary timeline for one learner.

Pulls events from every module, showing each viewer only what their role allows.
Counseling session notes and restricted protection cases never appear for staff
without access; restricted sessions by other counselors show as a bare entry.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.utils import timezone

from apps.core.roles import Cap

KINDS = {
    "violation": ("Violation", "bi-exclamation-triangle", "warning"),
    "discipline": ("Disciplinary case", "bi-hammer", "danger"),
    "protection": ("Protection case", "bi-shield-exclamation", "danger"),
    "counseling": ("Counseling", "bi-chat-heart", "primary"),
    "intervention": ("Intervention", "bi-life-preserver", "success"),
    "enrollment": ("Enrolment", "bi-mortarboard", "secondary"),
}


@dataclass
class TimelineEntry:
    when: datetime.datetime
    kind: str
    title: str
    detail: str = ""
    url: str | None = None

    @property
    def label(self) -> str:
        return KINDS[self.kind][0]

    @property
    def icon(self) -> str:
        return KINDS[self.kind][1]

    @property
    def style(self) -> str:
        return KINDS[self.kind][2]


def _at(day: datetime.date | None, time: datetime.time | None = None) -> datetime.datetime:
    day = day or timezone.localdate()
    naive = datetime.datetime.combine(day, time or datetime.time(8, 0))
    return timezone.make_aware(naive)


def visible_kinds(student, user) -> dict[str, tuple[str, str, str]]:
    """Timeline categories this user may see for this learner (drives the filter buttons)."""
    allowed = {
        "violation": user.has_cap(Cap.VIEW_DISCIPLINE) or student.is_advised_by(user),
        "discipline": user.has_cap(Cap.VIEW_DISCIPLINE),
        "protection": user.has_cap(Cap.VIEW_LRP),
        "counseling": user.has_cap(Cap.COUNSELING),
        "intervention": user.has_cap(Cap.VIEW_INTERVENTIONS),
        "enrollment": True,
    }
    return {key: meta for key, meta in KINDS.items() if allowed[key]}


def build_timeline(student, user, kinds: set[str] | None = None) -> list[TimelineEntry]:
    from apps.discipline.models import DisciplinaryCase
    from apps.protection.models import ProtectionCase

    wanted = kinds or set(KINDS)
    entries: list[TimelineEntry] = []
    adviser = student.is_advised_by(user)

    if "violation" in wanted and (user.has_cap(Cap.VIEW_DISCIPLINE) or adviser):
        for v in student.violations.select_related("offense_type"):
            entries.append(
                TimelineEntry(
                    when=_at(v.incident_date, v.incident_time),
                    kind="violation",
                    title=f"{v.offense_type.name} ({v.offense_type.get_level_display()})",
                    detail=f"Status: {v.get_status_display()}. Action: {v.action_taken or '—'}",
                    url=v.get_absolute_url(),
                )
            )

    if "discipline" in wanted and user.has_cap(Cap.VIEW_DISCIPLINE):
        for case in DisciplinaryCase.objects.filter(respondents=student):
            entries.append(
                TimelineEntry(
                    when=case.created_at,
                    kind="discipline",
                    title=f"{case.case_number}: {case.title}",
                    detail=f"Status: {case.get_status_display()}",
                    url=case.get_absolute_url(),
                )
            )
            if case.decision_date:
                entries.append(
                    TimelineEntry(
                        when=_at(case.decision_date),
                        kind="discipline",
                        title=f"{case.case_number}: decision issued",
                        url=case.get_absolute_url(),
                    )
                )

    if "protection" in wanted and user.has_cap(Cap.VIEW_LRP):
        cases = ProtectionCase.objects.visible_to(user).filter(parties__student=student).distinct()
        for case in cases.prefetch_related("parties"):
            roles = sorted(
                {p.get_role_display() for p in case.parties.all() if p.student_id == student.pk}
            )
            entries.append(
                TimelineEntry(
                    when=case.reported_at,
                    kind="protection",
                    title=f"{case.case_number} – {', '.join(roles)}",
                    detail=f"Status: {case.get_status_display()}",
                    url=case.get_absolute_url(),
                )
            )

    if "counseling" in wanted and user.has_cap(Cap.COUNSELING):
        for s in student.counseling_sessions.select_related("counselor"):
            if s.user_can_view(user):
                entries.append(
                    TimelineEntry(
                        when=_at(s.session_date, s.start_time),
                        kind="counseling",
                        title=f"{s.get_session_type_display()} – {s.get_primary_concern_display()}",
                        detail=f"{s.get_status_display()} with {s.counselor}",
                        url=s.get_absolute_url(),
                    )
                )
            else:
                entries.append(
                    TimelineEntry(
                        when=_at(s.session_date, s.start_time),
                        kind="counseling",
                        title="Restricted counseling session",
                        detail=f"Held by {s.counselor}",
                    )
                )

    if "intervention" in wanted and user.has_cap(Cap.VIEW_INTERVENTIONS):
        for plan in student.interventions.select_related("intervention_type"):
            entries.append(
                TimelineEntry(
                    when=_at(plan.start_date),
                    kind="intervention",
                    title=f"{plan.intervention_type.name}: {plan.title}",
                    detail=f"Status: {plan.get_status_display()}",
                    url=plan.get_absolute_url(),
                )
            )
            if plan.end_date:
                entries.append(
                    TimelineEntry(
                        when=_at(plan.end_date),
                        kind="intervention",
                        title=f"Intervention ended: {plan.title}",
                        detail=f"Outcome: {plan.get_outcome_display() or 'not assessed'}",
                        url=plan.get_absolute_url(),
                    )
                )

    if "enrollment" in wanted:
        for e in student.enrollments.select_related("section", "section__school_year"):
            entries.append(
                TimelineEntry(
                    when=_at(e.date_enrolled),
                    kind="enrollment",
                    title=f"Enrolled in {e.section}",
                    detail=e.get_status_display(),
                )
            )

    entries.sort(key=lambda entry: entry.when, reverse=True)
    return entries
