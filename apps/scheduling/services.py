"""Deadline follow-ups and the daily reminder digest."""

from __future__ import annotations

import datetime
from collections import defaultdict
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from .models import FollowUp


def end_of_day(day: datetime.date) -> datetime.datetime:
    """Deadlines counted in calendar days fall due at 11:59 PM local time."""
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time(23, 59)))


def upsert_rule_follow_up(
    obj,
    rule_key: str,
    *,
    title: str,
    due_at: datetime.datetime,
    module: str,
    done: bool = False,
    assigned_to=None,
    student=None,
    priority: str = FollowUp.Priority.HIGH,
    restricted: bool = False,
) -> FollowUp:
    """Creates or refreshes the follow-up for one deadline rule on one record.

    Open follow-ups track the latest due date and title; once the milestone is
    recorded (`done=True`) the follow-up is closed automatically.
    """
    ct = ContentType.objects.get_for_model(obj)
    follow_up = FollowUp.objects.filter(
        content_type=ct, object_id=obj.pk, rule_key=rule_key
    ).first()
    if follow_up is None:
        follow_up = FollowUp(
            content_type=ct,
            object_id=obj.pk,
            rule_key=rule_key,
            module=module,
            priority=priority,
            assigned_to=assigned_to,
            student=student,
        )
    changed = follow_up._state.adding
    if follow_up.restricted != restricted:
        follow_up.restricted = restricted
        changed = True
    if follow_up.status == FollowUp.Status.OPEN:
        if follow_up.title != title or follow_up.due_at != due_at:
            follow_up.title, follow_up.due_at = title, due_at
            changed = True
        if follow_up.assigned_to_id is None and assigned_to is not None:
            follow_up.assigned_to = assigned_to
            changed = True
        if done:
            follow_up.status = FollowUp.Status.DONE
            follow_up.completed_at = timezone.now()
            changed = True
    elif follow_up._state.adding:
        follow_up.title, follow_up.due_at = title, due_at
    if changed:
        follow_up._system_change = True
        follow_up.save()
    return follow_up


def cancel_open_rule_follow_ups(obj) -> int:
    ct = ContentType.objects.get_for_model(obj)
    pending = FollowUp.objects.open().filter(content_type=ct, object_id=obj.pk).exclude(rule_key="")
    count = 0
    for follow_up in pending:
        follow_up.status = FollowUp.Status.CANCELLED
        follow_up._system_change = True
        follow_up.save()
        count += 1
    return count


def send_reminder_digests(now: datetime.datetime | None = None) -> dict:
    """Emails each user their overdue and soon-due follow-ups. Run once a day."""
    now = now or timezone.now()
    horizon = now + timedelta(days=settings.REMINDER_LOOKAHEAD_DAYS)
    due = (
        FollowUp.objects.open()
        .filter(due_at__lte=horizon, assigned_to__isnull=False, assigned_to__is_active=True)
        .select_related("assigned_to")
        .order_by("due_at")
    )
    by_user: dict[int, list[FollowUp]] = defaultdict(list)
    for follow_up in due:
        by_user[follow_up.assigned_to_id].append(follow_up)

    users = get_user_model().objects.in_bulk(list(by_user))
    sent = skipped = 0
    for user_id, items in by_user.items():
        user = users[user_id]
        if not user.email:
            skipped += 1
            continue
        context = {
            "user": user,
            "overdue": [f for f in items if f.due_at < now],
            "upcoming": [f for f in items if f.due_at >= now],
            "site_name": settings.SITE_NAME,
        }
        # The email lists titles and due dates only; details stay behind sign-in.
        send_mail(
            subject=f"[{settings.SITE_NAME}] {len(items)} follow-up(s) need attention",
            message=render_to_string("scheduling/email_digest.txt", context),
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )
        sent += 1
    return {"users_emailed": sent, "users_without_email": skipped, "follow_ups": due.count()}
