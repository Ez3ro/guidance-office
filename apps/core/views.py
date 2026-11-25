from __future__ import annotations

import hmac
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import UpdateView

from apps.audit.models import AuditEvent
from apps.audit.services import log_event

from .crud import FormContextMixin
from .forms import AttachmentForm, BaseModelForm
from .models import Attachment, SchoolProfile
from .permissions import CapabilityRequiredMixin, ensure
from .roles import Cap, Role

ATTACHABLE_MODELS = {
    "protection.protectioncase",
    "discipline.disciplinarycase",
    "discipline.violationrecord",
    "counseling.counselingsession",
    "interventions.interventionplan",
}


@login_required
def dashboard(request):
    from apps.counseling.models import CounselingSession
    from apps.discipline.models import DisciplinaryCase, ViolationRecord
    from apps.interventions.models import InterventionPlan
    from apps.protection.models import ProtectionCase
    from apps.scheduling.models import CalendarEvent, FollowUp
    from apps.students.models import SchoolYear, Student

    user = request.user
    now = timezone.now()
    today = timezone.localdate()
    month_start = today.replace(day=1)
    hour = timezone.localtime(now).hour

    my_followups = FollowUp.objects.open().filter(assigned_to=user).order_by("due_at")
    visible_followups = FollowUp.objects.visible_to(user)
    events = CalendarEvent.objects.visible_to(user)
    ctx = {
        "greeting": "Good morning"
        if hour < 12
        else "Good afternoon"
        if hour < 18
        else "Good evening",
        "school_year": SchoolYear.current(),
        "my_followups": my_followups[:6],
        "overdue_count": my_followups.filter(due_at__lt=now).count(),
        "open_followup_count": my_followups.count(),
        "upcoming_events": events.filter(
            start__date__gt=today, start__date__lte=today + timedelta(days=7)
        ).order_by("start")[:6],
        "events_today": events.filter(start__date=today).order_by("start"),
        "overdue_items": visible_followups.overdue().order_by("due_at")[:8],
        "overdue_total": visible_followups.overdue().count(),
        "students_active": Student.objects.visible_to(user)
        .filter(status=Student.Status.ACTIVE)
        .distinct()
        .count(),
    }
    if user.has_cap(Cap.VIEW_LRP):
        visible_cases = ProtectionCase.objects.visible_to(user)
        ctx["lrp_open"] = visible_cases.open().count()
        ctx["lrp_new"] = visible_cases.filter(status=ProtectionCase.Status.REPORTED).count()
        ctx["lrp_deadlines"] = (
            visible_followups.open()
            .filter(
                module=FollowUp.Module.LRP,
                due_at__gte=now,
                due_at__lte=now + timedelta(days=2),
            )
            .order_by("due_at")[:6]
        )
    if user.has_cap(Cap.VIEW_DISCIPLINE):
        violations = ViolationRecord.objects.visible_to(user)
        ctx["violations_total"] = violations.count()
        ctx["violations_month"] = violations.filter(incident_date__gte=month_start).count()
        cases = DisciplinaryCase.objects.visible_to(user)
        S = DisciplinaryCase.Status
        pending = cases.filter(status__in=[S.FILED, S.NOTICE_SERVED]).count()
        ongoing = cases.filter(status__in=[S.DELIBERATION, S.DECIDED, S.APPEALED]).count()
        closed = cases.filter(status__in=[S.CLOSED, S.DISMISSED]).count()
        total = pending + ongoing + closed
        ctx["cases"] = {
            "pending": pending,
            "ongoing": ongoing,
            "closed": closed,
            "total": total,
            # Percentages for the pipeline bar (widths are applied by app.js: strict CSP).
            "pending_pct": round(pending * 100 / total) if total else 0,
            "ongoing_pct": round(ongoing * 100 / total) if total else 0,
            "closed_pct": round(closed * 100 / total) if total else 0,
        }
    if user.has_cap(Cap.COUNSELING):
        sessions = CounselingSession.objects.visible_to(user)
        scheduled = sessions.filter(status=CounselingSession.Status.SCHEDULED)
        ctx["awaiting_counseling"] = scheduled.filter(session_date__gte=today).count()
        ctx["sessions_today"] = scheduled.filter(session_date=today).order_by("start_time")
        mine = sessions.filter(counselor=user)
        ctx["sessions_month"] = mine.filter(
            session_date__gte=month_start, status=CounselingSession.Status.COMPLETED
        ).count()
    if user.has_cap(Cap.VIEW_INTERVENTIONS):
        plans = InterventionPlan.objects.visible_to(user)
        ctx["awaiting_intervention"] = plans.filter(status=InterventionPlan.Status.PLANNED).count()
        ctx["under_monitoring"] = plans.filter(status=InterventionPlan.Status.ONGOING).count()
    if user.role == Role.TEACHER:
        ctx["advisees_count"] = Student.objects.visible_to(user).count()
        ctx["my_reports"] = ProtectionCase.objects.filter(created_by=user).order_by("-reported_at")[
            :5
        ]
    # "Needs attention" = overdue follow-ups plus DO 006 deadlines falling due within 48 hours.
    ctx["attention_count"] = ctx["overdue_total"] + len(ctx.get("lrp_deadlines", []))
    ctx["today_count"] = len(ctx["events_today"]) + len(ctx.get("sessions_today", []))
    if user.has_cap(Cap.VIEW_AUDIT):
        ctx["recent_failed_logins"] = AuditEvent.objects.filter(
            action=AuditEvent.Action.LOGIN_FAILED, timestamp__gte=now - timedelta(days=1)
        ).count()
    return render(request, "core/dashboard.html", ctx)


def _attachment_parent(app_label: str, model: str, pk: int):
    if f"{app_label}.{model}" not in ATTACHABLE_MODELS:
        raise Http404
    ct = get_object_or_404(ContentType, app_label=app_label, model=model)
    parent = get_object_or_404(ct.model_class(), pk=pk)
    return ct, parent


@login_required
@require_POST
def attachment_upload(request, app_label: str, model: str, pk: int):
    ct, parent = _attachment_parent(app_label, model, pk)
    ensure(parent.user_can_edit(request.user))
    back = parent.get_absolute_url() + "#attachments"
    if not settings.ATTACHMENTS_ENABLED:
        messages.error(request, "File storage isn't configured, so attachments are switched off.")
        return redirect(back)
    form = AttachmentForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Choose a file to upload.")
        return redirect(back)
    upload = form.cleaned_data["file"]
    ext = Path(upload.name).suffix.lower()
    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        messages.error(
            request, f"{ext or 'That file type'} isn't allowed. Use PDF, JPG, PNG, DOCX or XLSX."
        )
    elif upload.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        messages.error(request, f"Files must be {settings.MAX_UPLOAD_SIZE_MB} MB or smaller.")
    else:
        Attachment.objects.create(
            content_type=ct,
            object_id=parent.pk,
            file=upload,
            original_name=upload.name[:255],
            size=upload.size,
            mime_type=(upload.content_type or "")[:100],
            description=form.cleaned_data["description"],
        )
        messages.success(request, "File attached.")
    return redirect(back)


@login_required
@require_GET
def attachment_download(request, pk: int):
    attachment = get_object_or_404(Attachment, pk=pk)
    parent = attachment.content_object
    ensure(parent is not None and parent.user_can_view(request.user))
    log_event(AuditEvent.Action.DOWNLOAD, obj=attachment)
    return FileResponse(
        attachment.file.open("rb"),
        as_attachment=True,
        filename=attachment.original_name,
        content_type=attachment.mime_type or "application/octet-stream",
    )


@login_required
@require_POST
def attachment_delete(request, pk: int):
    attachment = get_object_or_404(Attachment, pk=pk)
    parent = attachment.content_object
    ensure(parent is not None and parent.user_can_edit(request.user))
    attachment.file.delete(save=False)
    attachment.delete()
    messages.success(request, "Attachment removed.")
    return redirect(parent.get_absolute_url() + "#attachments")


@require_GET
def cron_daily(request):
    """Called once a day by Vercel Cron (see vercel.json), authenticated by CRON_SECRET."""
    secret = settings.CRON_SECRET
    supplied = request.headers.get("Authorization", "")
    if not secret or not hmac.compare_digest(supplied.encode(), f"Bearer {secret}".encode()):
        return JsonResponse({"error": "unauthorised"}, status=401)

    from apps.scheduling.services import send_reminder_digests

    result = send_reminder_digests()
    log_event(AuditEvent.Action.SYSTEM, object_repr="Daily reminder digest", changes=result)
    return JsonResponse({"ok": True, **result})


class SchoolProfileForm(BaseModelForm):
    class Meta:
        model = SchoolProfile
        fields = "__all__"


class SchoolProfileUpdateView(CapabilityRequiredMixin, FormContextMixin, UpdateView):
    required_caps = (Cap.MANAGE_SETTINGS,)
    form_class = SchoolProfileForm
    template_name = "crud/form.html"
    title = "School profile"
    intro = "These details appear in the header of printed forms and reports."
    success_url = reverse_lazy("core:school_profile")
    success_message = "School profile updated."

    def get_object(self, queryset=None):
        return SchoolProfile.load()

    def get_cancel_url(self) -> str:
        return reverse_lazy("core:dashboard")
