from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.scheduling.models import FollowUp
from apps.scheduling.services import (
    cancel_open_rule_follow_ups,
    end_of_day,
    upsert_rule_follow_up,
)

from .models import InterventionPlan


@receiver(post_save, sender=InterventionPlan)
def schedule_review(sender, instance: InterventionPlan, raw=False, **kwargs):
    if raw:
        return
    finished = instance.status in {
        InterventionPlan.Status.COMPLETED,
        InterventionPlan.Status.DISCONTINUED,
    }
    if not instance.target_end_date:
        if finished:
            cancel_open_rule_follow_ups(instance)
        return
    upsert_rule_follow_up(
        instance,
        "intervention.review",
        title=f"Review intervention #{instance.pk}: {instance.title}",
        due_at=end_of_day(instance.target_end_date),
        module=FollowUp.Module.INTERVENTION,
        done=finished,
        assigned_to=instance.responsible,
        student=instance.student,
        priority=FollowUp.Priority.NORMAL,
    )
