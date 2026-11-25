"""Automatic audit logging for registered models, sign-ins and sign-outs."""

from __future__ import annotations

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import m2m_changed, post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import AuditEvent
from .registry import is_audited
from .services import diff, log_event, snapshot


@receiver(pre_save)
def capture_previous_state(sender, instance, raw=False, **kwargs):
    if raw or not is_audited(sender):
        return
    previous = None
    if instance.pk is not None and not instance._state.adding:
        try:
            previous = snapshot(sender._base_manager.get(pk=instance.pk))
        except sender.DoesNotExist:
            previous = None
    instance._audit_previous = previous


@receiver(post_save)
def log_save(sender, instance, created, raw=False, **kwargs):
    if raw or not is_audited(sender):
        return
    previous = None if created else getattr(instance, "_audit_previous", None)
    changes = diff(previous, snapshot(instance))
    if not created and not changes:
        return
    log_event(
        AuditEvent.Action.CREATE if created else AuditEvent.Action.UPDATE,
        obj=instance,
        changes=changes,
    )


@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if not is_audited(sender):
        return
    log_event(AuditEvent.Action.DELETE, obj=instance)


@receiver(m2m_changed)
def log_m2m(sender, instance, action, model, pk_set, **kwargs):
    if not is_audited(type(instance)) or action not in {"post_add", "post_remove", "post_clear"}:
        return
    field_name = next(
        (f.name for f in type(instance)._meta.many_to_many if f.remote_field.through is sender),
        model._meta.model_name,
    )
    verb = {"post_add": "added", "post_remove": "removed", "post_clear": "cleared"}[action]
    log_event(
        AuditEvent.Action.UPDATE,
        obj=instance,
        changes={field_name: {verb: sorted(pk_set) if pk_set else []}},
    )


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    log_event(AuditEvent.Action.LOGIN, actor=user, request=request, object_repr=user.username)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    if user is not None:
        log_event(AuditEvent.Action.LOGOUT, actor=user, request=request, object_repr=user.username)


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request=None, **kwargs):
    username = str(credentials.get("username", ""))[:150]
    log_event(
        AuditEvent.Action.LOGIN_FAILED,
        request=request,
        object_repr=username,
        changes={"username": username},
    )
