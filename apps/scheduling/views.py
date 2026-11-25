from __future__ import annotations

import calendar
import datetime
from collections import defaultdict

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.crud import (
    Action,
    GenericCreateView,
    GenericDetailView,
    GenericListView,
    GenericUpdateView,
    ListFilter,
    is_htmx,
    safe_next_url,
)
from apps.core.permissions import ensure, require_cap
from apps.core.roles import Cap

from .forms import CalendarEventForm, FollowUpForm
from .models import CalendarEvent, FollowUp


def _month_from_request(request) -> tuple[int, int]:
    today = timezone.localdate()
    try:
        year = int(request.GET.get("year", today.year))
        month = int(request.GET.get("month", today.month))
    except ValueError:
        return today.year, today.month
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        return today.year, today.month
    return year, month


@require_cap()
def calendar_month(request):
    from apps.counseling.models import CounselingSession

    user = request.user
    year, month = _month_from_request(request)
    weeks = calendar.Calendar(firstweekday=6).monthdatescalendar(year, month)
    first, last = weeks[0][0], weeks[-1][-1]
    items: dict[datetime.date, list[dict]] = defaultdict(list)

    events = CalendarEvent.objects.visible_to(user).filter(
        start__date__gte=first, start__date__lte=last
    )
    for event in events:
        start = timezone.localtime(event.start)
        items[start.date()].append(
            {
                "kind": "event",
                "time": start.time(),
                "title": event.title,
                "url": event.get_absolute_url(),
            }
        )

    if user.has_cap(Cap.COUNSELING):
        sessions = (
            CounselingSession.objects.visible_to(user)
            .filter(session_date__gte=first, session_date__lte=last)
            .exclude(status=CounselingSession.Status.CANCELLED)
            .prefetch_related("students")
        )
        for session in sessions:
            names = ", ".join(s.display_name for s in session.students.all()[:2])
            items[session.session_date].append(
                {
                    "kind": "session",
                    "time": session.start_time,
                    "title": f"Session: {names}",
                    "url": session.get_absolute_url(),
                }
            )

    follow_ups = (
        FollowUp.objects.open()
        .visible_to(user)
        .filter(due_at__date__gte=first, due_at__date__lte=last)
    )
    for follow_up in follow_ups:
        due = timezone.localtime(follow_up.due_at)
        items[due.date()].append(
            {
                "kind": "overdue" if follow_up.is_overdue else "due",
                "time": due.time(),
                "title": f"Due: {follow_up.title}",
                "url": follow_up.get_absolute_url(),
            }
        )

    for day_items in items.values():
        day_items.sort(key=lambda item: item["time"] or datetime.time.min)

    prev_month = datetime.date(year, month, 1) - datetime.timedelta(days=1)
    next_month = datetime.date(year, month, 28) + datetime.timedelta(days=7)
    ctx = {
        "weeks": [[(day, items.get(day, [])) for day in week] for week in weeks],
        "month_label": datetime.date(year, month, 1).strftime("%B %Y"),
        "month": month,
        "today": timezone.localdate(),
        "prev": {"year": prev_month.year, "month": prev_month.month},
        "next": {"year": next_month.year, "month": next_month.month},
        "weekday_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    }
    template = (
        "scheduling/calendar.html#calendar" if is_htmx(request) else "scheduling/calendar.html"
    )
    return render(request, template, ctx)


class EventCreateView(GenericCreateView):
    model = CalendarEvent
    form_class = CalendarEventForm
    title = "New calendar event"
    success_message = "Event added to the calendar."

    def get_initial(self):
        initial = super().get_initial()
        day = self.request.GET.get("date")
        if day:
            try:
                parsed = datetime.date.fromisoformat(day)
                initial["start"] = timezone.make_aware(
                    datetime.datetime.combine(parsed, datetime.time(9, 0))
                )
            except ValueError:
                pass
        return initial

    def get_cancel_url(self):
        return reverse("scheduling:calendar")


class EventDetailView(GenericDetailView):
    model = CalendarEvent
    log_view = False

    def get_queryset(self):
        return CalendarEvent.objects.visible_to(self.request.user)

    def get_detail_sections(self):
        e = self.object
        return [
            (
                e.title,
                [
                    ("Type", e.get_event_type_display()),
                    ("Starts", e.start),
                    ("Ends", e.end),
                    ("Location", e.location),
                    ("Visible to", e.get_visibility_display()),
                    ("Participants", e.participants),
                    ("Learners", e.students),
                    ("Description", e.description),
                    ("Created by", e.created_by),
                ],
            )
        ]

    def get_actions(self):
        if self.object.user_can_edit(self.request.user):
            return [
                Action(
                    "Edit", reverse("scheduling:event_update", args=[self.object.pk]), "bi-pencil"
                )
            ]
        return []


class EventUpdateView(GenericUpdateView):
    model = CalendarEvent
    form_class = CalendarEventForm
    title = "Edit calendar event"
    success_message = "Event updated."

    def get_queryset(self):
        return CalendarEvent.objects.visible_to(self.request.user)


class FollowUpListView(GenericListView):
    model = FollowUp
    template_name = "scheduling/followup_list.html"
    title = "Follow-ups"
    columns = [
        ("Due", "due_at"),
        ("Follow-up", "title"),
        ("Assigned to", "assigned_to"),
        ("Module", "get_module_display"),
        ("Priority", "get_priority_display"),
        ("Status", "state"),
        ("", ""),
    ]
    search_fields = ["title"]
    search_placeholder = "Search follow-ups…"
    create_url_name = "scheduling:followup_create"
    create_label = "New follow-up"
    empty_message = "No follow-ups match. Nice."

    def get_filters(self):
        return [
            ListFilter("scope", "Show", [("mine", "Assigned to me"), ("all", "All I can see")]),
            ListFilter("status", "Status", FollowUp.Status.choices),
            ListFilter("module", "Module", FollowUp.Module.choices),
        ]

    def apply_filter(self, qs, flt, value):
        if flt.param == "scope":
            return qs.filter(assigned_to=self.request.user) if value == "mine" else qs
        return super().apply_filter(qs, flt, value)

    def get_queryset(self):
        qs = super().get_queryset().select_related("assigned_to")
        if "status" not in self.request.GET:
            qs = qs.filter(status=FollowUp.Status.OPEN)
        if "scope" not in self.request.GET:
            qs = qs.filter(assigned_to=self.request.user)
        return qs.order_by("due_at")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        for flt in ctx["filters"]:
            if flt.param == "scope" and not flt.current:
                flt.current = "mine"
            if flt.param == "status" and "status" not in self.request.GET:
                flt.current = FollowUp.Status.OPEN
        ctx["row_template"] = "scheduling/_followup_row.html"
        return ctx


class FollowUpCreateView(GenericCreateView):
    model = FollowUp
    form_class = FollowUpForm
    title = "New follow-up"
    success_message = "Follow-up created."

    def get_initial(self):
        initial = super().get_initial()
        if self.request.GET.get("student"):
            initial["student"] = self.request.GET["student"]
        return initial

    def get_success_url(self):
        return reverse("scheduling:followups")

    def get_cancel_url(self):
        return reverse("scheduling:followups")


class FollowUpUpdateView(GenericUpdateView):
    model = FollowUp
    form_class = FollowUpForm
    title = "Edit follow-up"
    success_message = "Follow-up updated."

    def get_queryset(self):
        return FollowUp.objects.visible_to(self.request.user)

    def get_success_url(self):
        return reverse("scheduling:followups")

    def get_cancel_url(self):
        return reverse("scheduling:followups")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.object.related_url:
            ctx["extra_actions"] = [
                Action("Open related record", self.object.related_url, "bi-box-arrow-up-right")
            ]
        return ctx


@require_cap()
@require_POST
def followup_done(request, pk: int):
    follow_up = get_object_or_404(FollowUp.objects.visible_to(request.user), pk=pk)
    ensure(follow_up.status == FollowUp.Status.OPEN)
    follow_up.mark_done(request.user)
    if is_htmx(request):
        return render(
            request,
            "scheduling/_followup_row.html",
            {"obj": follow_up, "columns": FollowUpListView.columns},
        )
    messages.success(request, "Marked as done.")
    return redirect(safe_next_url(request) or reverse("scheduling:followups"))
