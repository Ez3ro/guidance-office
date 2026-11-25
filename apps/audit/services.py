from __future__ import annotations

import datetime
import decimal
import uuid

from django.db import models

from apps.core.fields import EncryptedTextField
from apps.core.net import get_client_ip
from apps.core.request_context import get_current_request

from .models import AuditEvent
from .registry import IGNORED_FIELDS

ENCRYPTED_PLACEHOLDER = "(confidential)"


def _jsonable(value):
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, datetime.datetime | datetime.date | datetime.time):
        return value.isoformat()
    if isinstance(value, decimal.Decimal | uuid.UUID):
        return str(value)
    if hasattr(value, "name") and hasattr(value, "url"):  # FieldFile
        return value.name or None
    return str(value)


def snapshot(instance: models.Model) -> dict:
    """Current values of concrete fields (FKs as ids, encrypted fields masked)."""
    data = {}
    for field in instance._meta.concrete_fields:
        if field.name in IGNORED_FIELDS:
            continue
        value = field.value_from_object(instance)
        if isinstance(field, EncryptedTextField):
            data[field.attname] = ENCRYPTED_PLACEHOLDER if value else ""
            # keep a private hash-free marker so changes can be detected
            data[f"__changed__{field.attname}"] = value
        else:
            data[field.attname] = _jsonable(value)
    return data


def diff(old: dict | None, new: dict) -> dict:
    changes = {}
    for key, new_value in new.items():
        if key.startswith("__changed__"):
            continue
        marker = f"__changed__{key}"
        if marker in new:
            old_raw = (old or {}).get(marker)
            if old is None:
                if new[marker]:
                    changes[key] = [None, ENCRYPTED_PLACEHOLDER]
            elif old_raw != new[marker]:
                changes[key] = [ENCRYPTED_PLACEHOLDER, ENCRYPTED_PLACEHOLDER + " – changed"]
            continue
        old_value = None if old is None else old.get(key)
        if old is None:
            if new_value not in (None, ""):
                changes[key] = [None, new_value]
        elif old_value != new_value:
            changes[key] = [old_value, new_value]
    return changes


def safe_repr(obj) -> str:
    """Short description for the log. Models may define audit_repr() to avoid names."""
    if obj is None:
        return ""
    if hasattr(obj, "audit_repr"):
        return str(obj.audit_repr())[:255]
    return f"{obj._meta.verbose_name} #{obj.pk}"[:255]


def log_event(
    action: str,
    *,
    obj: models.Model | None = None,
    changes: dict | None = None,
    object_repr: str | None = None,
    actor=None,
    request=None,
) -> AuditEvent:
    request = request or get_current_request()
    if actor is None and request is not None:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            actor = user
    return AuditEvent.objects.create(
        action=action,
        actor=actor,
        actor_username=getattr(actor, "username", "") or "",
        model_label=obj._meta.label_lower if obj is not None else "",
        object_id=str(obj.pk) if obj is not None and obj.pk is not None else "",
        object_repr=object_repr if object_repr is not None else safe_repr(obj),
        changes=changes or {},
        ip_address=get_client_ip(request) if request is not None else None,
        user_agent=(request.headers.get("User-Agent", "")[:255] if request is not None else ""),
        path=(request.path[:255] if request is not None else ""),
    )


def log_view(obj: models.Model) -> AuditEvent:
    return log_event(AuditEvent.Action.VIEW, obj=obj)
