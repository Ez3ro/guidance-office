import csv

from django.http import StreamingHttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.core.crud import GenericListView, ListFilter
from apps.core.permissions import require_cap
from apps.core.roles import Cap

from .models import AuditEvent
from .registry import AUDITED_MODELS
from .services import log_event


def _record_type_choices():
    choices = {m._meta.label_lower: m._meta.verbose_name.title() for m in AUDITED_MODELS}
    choices["core.attachment"] = "Attachment"
    return sorted(choices.items(), key=lambda item: item[1])


class AuditEventListView(GenericListView):
    model = AuditEvent
    required_caps = (Cap.VIEW_AUDIT,)
    template_name = "audit/event_list.html"
    title = "Audit log"
    paginate_by = 50
    row_template = "audit/_row.html"
    columns = [
        ("When", "timestamp"),
        ("User", "actor_username"),
        ("Action", "get_action_display"),
        ("Record", "model_name"),
        ("Description", "object_repr"),
        ("IP address", "ip_address"),
        ("Details", "changes"),
    ]
    search_fields = ["actor_username", "object_repr", "object_id"]
    search_placeholder = "Search user, record or ID…"

    def get_filters(self):
        return [
            ListFilter("action", "Action", AuditEvent.Action.choices),
            ListFilter("model_label", "Record type", _record_type_choices()),
        ]

    def get_queryset(self):
        qs = super().get_queryset()
        start = parse_date(self.request.GET.get("from", "") or "")
        end = parse_date(self.request.GET.get("to", "") or "")
        if start:
            qs = qs.filter(timestamp__date__gte=start)
        if end:
            qs = qs.filter(timestamp__date__lte=end)
        return qs.select_related("actor")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["row_template"] = self.row_template
        return ctx


class _Echo:
    def write(self, value):
        return value


@require_cap(Cap.VIEW_AUDIT)
def export_csv(request):
    view = AuditEventListView()
    view.setup(request)
    events = view.get_queryset()
    log_event(
        AuditEvent.Action.EXPORT,
        object_repr="Audit log CSV export",
        changes={k: v for k, v in request.GET.items()},
    )
    writer = csv.writer(_Echo())

    def rows():
        yield writer.writerow(
            [
                "timestamp",
                "user",
                "action",
                "record_type",
                "record_id",
                "description",
                "ip",
                "changes",
            ]
        )
        for e in events.iterator(chunk_size=500):
            yield writer.writerow(
                [
                    timezone.localtime(e.timestamp).isoformat(),
                    e.actor_username,
                    e.action,
                    e.model_label,
                    e.object_id,
                    e.object_repr,
                    e.ip_address or "",
                    e.changes,
                ]
            )

    stamp = timezone.localdate().isoformat()
    response = StreamingHttpResponse(rows(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="audit-log-{stamp}.csv"'
    return response
