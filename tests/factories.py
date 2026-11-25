"""Minimal helpers for building test data (no extra dependencies)."""

from __future__ import annotations

import datetime
import itertools

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.core.roles import Role
from apps.discipline.models import OffenseType
from apps.protection.models import ConcernCategory, ConcernType, ProtectionCase
from apps.students.models import Enrollment, SchoolYear, Section, Student

_seq = itertools.count(1)


def make_user(role: str = Role.TEACHER, **extra):
    n = next(_seq)
    user = get_user_model()(
        username=extra.pop("username", f"user{n}"),
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", f"User{n}"),
        email=extra.pop("email", f"user{n}@example.com"),
        role=role,
        **extra,
    )
    user.set_password("Correct-Horse-Battery-9")
    user.save()
    return user


def current_school_year() -> SchoolYear:
    sy = SchoolYear.current()
    if sy:
        return sy
    today = timezone.localdate()
    return SchoolYear.objects.create(
        name=f"{today.year}-{today.year + 1}",
        start_date=today - datetime.timedelta(days=60),
        end_date=today + datetime.timedelta(days=240),
        is_current=True,
    )


def make_section(adviser=None, grade="7", name=None) -> Section:
    return Section.objects.create(
        school_year=current_school_year(),
        grade_level=grade,
        name=name or f"Section {next(_seq)}",
        adviser=adviser,
    )


def make_student(section: Section | None = None, sex: str = "F", **extra) -> Student:
    n = next(_seq)
    student = Student.objects.create(
        first_name=extra.pop("first_name", "Learner"),
        last_name=extra.pop("last_name", f"Test{n}"),
        sex=sex,
        lrn=extra.pop("lrn", f"{n:012d}"),
        **extra,
    )
    if section:
        Enrollment.objects.create(student=student, section=section)
    return student


def concern(
    name="Verbal bullying", category=ConcernCategory.BULLYING, sensitive=False
) -> ConcernType:
    obj, _ = ConcernType.objects.get_or_create(
        category=category, name=name, defaults={"is_sensitive": sensitive}
    )
    return obj


def offense(code="L1-03", level=1, **extra) -> OffenseType:
    obj, _ = OffenseType.objects.get_or_create(
        code=code, defaults={"name": extra.pop("name", f"Offence {code}"), "level": level, **extra}
    )
    return obj


def make_case(received_by=None, **extra) -> ProtectionCase:
    return ProtectionCase.objects.create(
        received_by=received_by,
        narrative=extra.pop("narrative", "Learner disclosed repeated name-calling."),
        **extra,
    )
