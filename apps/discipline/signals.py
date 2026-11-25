"""Due-process deadlines from DO 006, s. 2026 become follow-ups automatically."""

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.scheduling.models import FollowUp
from apps.scheduling.services import cancel_open_rule_follow_ups, end_of_day, upsert_rule_follow_up

from .models import DisciplinaryCase


@receiver(post_save, sender=DisciplinaryCase)
def sync_due_process_follow_ups(sender, instance: DisciplinaryCase, raw=False, **kwargs):
    if raw:
        return
    case = instance
    if case.status in {DisciplinaryCase.Status.CLOSED, DisciplinaryCase.Status.DISMISSED}:
        cancel_open_rule_follow_ups(case)
        return
    handler = case.handled_by or case.created_by
    past_answer_stage = case.status in {
        DisciplinaryCase.Status.DELIBERATION,
        DisciplinaryCase.Status.DECIDED,
        DisciplinaryCase.Status.APPEALED,
    }
    if case.notice_served_on:
        upsert_rule_follow_up(
            case,
            "discipline.answer_due",
            title=(
                f"{case.case_number}: respondent's answer due "
                f"({settings.DUE_PROCESS_ANSWER_DAYS} calendar days from notice)"
            ),
            due_at=end_of_day(case.answer_due),
            module=FollowUp.Module.DISCIPLINE,
            done=bool(case.answer_received_on) or past_answer_stage,
            assigned_to=handler,
        )
    if case.decision_date:
        upsert_rule_follow_up(
            case,
            "discipline.appeal_period",
            title=(
                f"{case.case_number}: appeal period ends "
                f"({case.appeal_days} days, to the {case.appeal_body})"
            ),
            due_at=end_of_day(case.appeal_deadline),
            module=FollowUp.Module.DISCIPLINE,
            done=bool(case.appeal_filed_on),
            assigned_to=handler,
            priority=FollowUp.Priority.NORMAL,
        )
