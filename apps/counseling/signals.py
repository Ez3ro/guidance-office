from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.scheduling.models import FollowUp
from apps.scheduling.services import end_of_day, upsert_rule_follow_up

from .models import CounselingSession


@receiver(post_save, sender=CounselingSession)
def schedule_next_session_reminder(sender, instance: CounselingSession, raw=False, **kwargs):
    if raw or not instance.next_session_date:
        return
    upsert_rule_follow_up(
        instance,
        "counseling.next_session",
        title=f"Follow-up counseling session (from session #{instance.pk})",
        due_at=end_of_day(instance.next_session_date),
        module=FollowUp.Module.COUNSELING,
        assigned_to=instance.counselor,
        priority=FollowUp.Priority.NORMAL,
    )
