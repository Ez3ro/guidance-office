"""Roles and what each role may do.

Access is capability-based: views ask "can this user do X?" rather than checking
role names, so the matrix below is the single place to change who sees what.
See docs/SECURITY.md for the same matrix in table form.
"""

from __future__ import annotations

from enum import StrEnum

from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "System Administrator"
    SCHOOL_HEAD = "school_head", "School Head"
    COUNSELOR = "counselor", "Guidance Counselor (RGC)"
    GUIDANCE_DESIGNATE = "guidance_designate", "Guidance Designate / Advocate"
    LFO = "lfo", "Learner Formation Officer"
    TEACHER = "teacher", "Teacher / Class Adviser"


class Cap(StrEnum):
    VIEW_ALL_STUDENTS = "view_all_students"
    EDIT_STUDENTS = "edit_students"
    VIEW_CONFIDENTIAL_PROFILE = "view_confidential_profile"
    COUNSELING = "counseling"
    VIEW_DISCIPLINE = "view_discipline"
    MANAGE_DISCIPLINE = "manage_discipline"
    REPORT_INCIDENT = "report_incident"
    VIEW_LRP = "view_lrp"
    MANAGE_LRP = "manage_lrp"
    VIEW_RESTRICTED_LRP = "view_restricted_lrp"
    REPORT_CONCERN = "report_concern"
    VIEW_INTERVENTIONS = "view_interventions"
    MANAGE_INTERVENTIONS = "manage_interventions"
    VIEW_REPORTS = "view_reports"
    MANAGE_USERS = "manage_users"
    VIEW_AUDIT = "view_audit"
    MANAGE_SETTINGS = "manage_settings"


_GUIDANCE = frozenset(
    {
        Cap.VIEW_ALL_STUDENTS,
        Cap.EDIT_STUDENTS,
        Cap.VIEW_CONFIDENTIAL_PROFILE,
        Cap.COUNSELING,
        Cap.VIEW_DISCIPLINE,
        Cap.MANAGE_DISCIPLINE,
        Cap.REPORT_INCIDENT,
        Cap.VIEW_LRP,
        Cap.MANAGE_LRP,
        Cap.VIEW_RESTRICTED_LRP,
        Cap.REPORT_CONCERN,
        Cap.VIEW_INTERVENTIONS,
        Cap.MANAGE_INTERVENTIONS,
        Cap.VIEW_REPORTS,
    }
)

ROLE_CAPABILITIES: dict[str, frozenset[Cap]] = {
    # IT/system administration: users, settings and the audit trail, but no access to
    # counseling notes, case narratives or confidential profile fields.
    Role.ADMIN: frozenset(
        {
            Cap.VIEW_ALL_STUDENTS,
            Cap.EDIT_STUDENTS,
            Cap.MANAGE_USERS,
            Cap.VIEW_AUDIT,
            Cap.MANAGE_SETTINGS,
            Cap.REPORT_CONCERN,
        }
    ),
    # Chairs the Child Protection Committee and receives investigation reports.
    # Sees reports and case files but not counseling session notes.
    Role.SCHOOL_HEAD: frozenset(
        {
            Cap.VIEW_ALL_STUDENTS,
            Cap.VIEW_DISCIPLINE,
            Cap.MANAGE_DISCIPLINE,
            Cap.REPORT_INCIDENT,
            Cap.VIEW_LRP,
            Cap.MANAGE_LRP,
            Cap.VIEW_RESTRICTED_LRP,
            Cap.REPORT_CONCERN,
            Cap.VIEW_INTERVENTIONS,
            Cap.VIEW_REPORTS,
            Cap.VIEW_AUDIT,
        }
    ),
    Role.COUNSELOR: _GUIDANCE,
    Role.GUIDANCE_DESIGNATE: _GUIDANCE,
    # Manages learner behaviour (DO 006, s. 2026) and may complete risk assessments.
    Role.LFO: frozenset(
        {
            Cap.VIEW_ALL_STUDENTS,
            Cap.VIEW_DISCIPLINE,
            Cap.MANAGE_DISCIPLINE,
            Cap.REPORT_INCIDENT,
            Cap.VIEW_LRP,
            Cap.MANAGE_LRP,
            Cap.REPORT_CONCERN,
            Cap.VIEW_INTERVENTIONS,
            Cap.MANAGE_INTERVENTIONS,
            Cap.VIEW_REPORTS,
        }
    ),
    # Sees their own advisory class, can report incidents and concerns.
    Role.TEACHER: frozenset({Cap.REPORT_INCIDENT, Cap.REPORT_CONCERN}),
}

# Staff who sit on the Child Protection Committee get case access on top of their role.
CPC_CAPABILITIES = frozenset({Cap.VIEW_LRP, Cap.MANAGE_LRP, Cap.REPORT_CONCERN})


def capabilities_for(role: str, is_cpc_member: bool = False) -> frozenset[Cap]:
    caps = ROLE_CAPABILITIES.get(role, frozenset())
    if is_cpc_member:
        caps = caps | CPC_CAPABILITIES
    return caps
