"""Template helpers available in every template (registered as builtins in settings)."""

from __future__ import annotations

import datetime

from django import template
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

BADGE_STYLES = {
    # generic workflow states
    "open": "warning",
    "overdue": "danger",
    "due_soon": "warning",
    "done": "success",
    "met": "success",
    "missed": "danger",
    "pending": "secondary",
    "cancelled": "secondary",
    "completed": "success",
    "closed": "secondary",
    "resolved": "success",
    "dismissed": "secondary",
    "escalated": "info",
    "scheduled": "info",
    "no_show": "warning",
    "planned": "info",
    "ongoing": "primary",
    "discontinued": "secondary",
    # protection cases
    "reported": "danger",
    "assessed": "warning",
    "intake_referred": "warning",
    "fact_finding": "primary",
    "findings_submitted": "primary",
    "forwarded": "info",
    # disciplinary cases
    "filed": "warning",
    "notice_served": "warning",
    "deliberation": "primary",
    "decided": "info",
    "appealed": "danger",
    # risk
    "low": "success",
    "moderate": "warning",
    "high": "danger",
    "critical": "danger",
    # offence levels
    "1": "secondary",
    "2": "warning",
    "3": "danger",
}


@register.filter
def resolve(obj, path):
    """Follows a dotted path ("student.full_name"), calling zero-argument methods."""
    value = obj
    for part in str(path).split("."):
        if value is None:
            return None
        value = getattr(value, part, None)
        if callable(value) and not hasattr(value, "all"):
            value = value()
    return value


@register.filter
def cell(value):
    """Formats a value for a table cell or detail row."""
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        if value:
            return mark_safe('<i class="bi bi-check-lg text-success" aria-label="Yes"></i>')
        return "—"
    if isinstance(value, datetime.datetime):
        return date_format(timezone.localtime(value), "M j, Y g:i A")
    if isinstance(value, datetime.date):
        return date_format(value, "M j, Y")
    if hasattr(value, "all"):
        items = [str(item) for item in value.all()]
        return ", ".join(items) if items else "—"
    return value


@register.simple_tag
def badge(value, label=None):
    style = BADGE_STYLES.get(str(value), "secondary")
    return format_html('<span class="badge text-bg-{}">{}</span>', style, label or value)


@register.simple_tag
def attachments_panel(obj, user):
    """Context for templates/includes/attachments.html."""
    from apps.core.models import Attachment

    ct = ContentType.objects.get_for_model(obj)
    return {
        "items": Attachment.objects.filter(content_type=ct, object_id=obj.pk),
        "upload_url": reverse("core:attachment_upload", args=[ct.app_label, ct.model, obj.pk]),
        "enabled": settings.ATTACHMENTS_ENABLED,
        "can_edit": obj.user_can_edit(user) if hasattr(obj, "user_can_edit") else False,
        "max_mb": settings.MAX_UPLOAD_SIZE_MB,
        "extensions": ", ".join(settings.ALLOWED_UPLOAD_EXTENSIONS),
    }


@register.filter
def field_type(bound_field) -> str:
    return bound_field.field.widget.__class__.__name__


@register.filter
def checkbox_groups(form, name):
    method = getattr(form, "checkbox_groups", None)
    return method(name) if method else None


@register.filter
def localdt(value):
    if isinstance(value, datetime.datetime):
        return timezone.localtime(value)
    return value
