"""DO 006, s. 2026 deadlines for protection cases become follow-ups automatically."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.scheduling.models import FollowUp
from apps.scheduling.services import cancel_open_rule_follow_ups, end_of_day, upsert_rule_follow_up

from .models import ProtectionCase, RiskAssessment


def sync_case_follow_ups(case: ProtectionCase) -> None:
    if not case.is_open:
        cancel_open_rule_follow_ups(case)
        return
    common = {
        "module": FollowUp.Module.LRP,
        "assigned_to": case.received_by,
        "restricted": case.restricted,
    }
    number = case.case_number
    upsert_rule_follow_up(
        case,
        "lrp.risk_assessment",
        title=f"{number}: complete the Initial Risk Assessment (Annex H)",
        due_at=case.risk_assessment_target,
        done=case.risk_assessments.exists(),
        priority=FollowUp.Priority.URGENT,
        **common,
    )
    upsert_rule_follow_up(
        case,
        "lrp.intake_48h",
        title=f"{number}: refer the Incident Report and Intake Sheet to the disciplining authority (48 h)",
        due_at=case.intake_due_at,
        done=bool(case.intake_referred_at),
        priority=FollowUp.Priority.URGENT,
        **common,
    )
    if case.fact_finding_started_on:
        upsert_rule_follow_up(
            case,
            "lrp.findings_10d",
            title=f"{number}: submit fact-finding findings to the School Head (10 calendar days)",
            due_at=end_of_day(case.fact_finding_due),
            done=bool(case.findings_submitted_on),
            **common,
        )
        upsert_rule_follow_up(
            case,
            "lrp.forward_30d",
            title=f"{number}: forward investigation results to the SDS and RD (30 days from report)",
            due_at=end_of_day(case.forward_due),
            done=bool(case.forwarded_to_sds_rd_on),
            **common,
        )


@receiver(post_save, sender=ProtectionCase)
def on_case_saved(sender, instance: ProtectionCase, raw=False, **kwargs):
    if not raw:
        sync_case_follow_ups(instance)


@receiver(post_save, sender=RiskAssessment)
def on_risk_assessment_saved(sender, instance: RiskAssessment, raw=False, **kwargs):
    if raw:
        return
    case = instance.case
    if case.status == ProtectionCase.Status.REPORTED:
        case.status = ProtectionCase.Status.ASSESSED
        case.save()  # triggers sync_case_follow_ups
    else:
        sync_case_follow_ups(case)
