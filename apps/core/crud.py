"""Small generic list/detail/form views shared by every module.

Each module declares columns, filters and permissions; the shared templates in
templates/crud/ render them. Lists support HTMX live search and filtering.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from .permissions import CapabilityRequiredMixin
from .roles import Cap


@dataclass
class ListFilter:
    param: str
    label: str
    choices: list[tuple[Any, str]]
    lookup: str | None = None
    current: str = ""
    all_label: str = ""  # text of the "no filter" option, e.g. "All grade levels"


@dataclass
class Action:
    label: str
    url: str
    icon: str = ""
    style: str = "outline-secondary"
    extra: dict = field(default_factory=dict)


def is_htmx(request) -> bool:
    return (
        request.headers.get("HX-Request") == "true" and request.headers.get("HX-Boosted") != "true"
    )


def safe_next_url(request, param: str = "next") -> str | None:
    """Returns ?next= only if it points back to this site (no open redirects or javascript:)."""
    from django.utils.http import url_has_allowed_host_and_scheme

    candidate = request.GET.get(param) or request.POST.get(param) or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return candidate
    return None


class ScopedQuerysetMixin:
    """Limits querysets to what the user may see, via QuerySet.visible_to(user)."""

    def get_queryset(self):
        qs = super().get_queryset()
        if hasattr(qs, "visible_to"):
            qs = qs.visible_to(self.request.user)
        return qs


class ObjectPermissionMixin:
    """Checks obj.user_can_view / obj.user_can_edit and logs views of sensitive records."""

    require_edit = False
    log_view = False

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        user = self.request.user
        check = "user_can_edit" if self.require_edit else "user_can_view"
        if hasattr(obj, check) and not getattr(obj, check)(user):
            raise PermissionDenied
        if self.log_view and self.request.method == "GET":
            from apps.audit.services import log_view

            log_view(obj)
        return obj


class GenericListView(CapabilityRequiredMixin, ScopedQuerysetMixin, ListView):
    template_name = "crud/list.html"
    paginate_by = 25
    title = ""
    subtitle = ""
    columns: list[tuple[str, str]] = []
    search_fields: list[str] = []
    search_placeholder = "Search…"
    filters: list[ListFilter] = []
    create_url_name: str | None = None
    create_label = "New"
    create_caps: tuple[Cap, ...] = ()
    empty_message = "Nothing here yet."

    def get_filters(self) -> list[ListFilter]:
        return [ListFilter(**vars(f)) for f in self.filters]

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        if q and self.search_fields:
            condition = Q()
            for name in self.search_fields:
                condition |= Q(**{f"{name}__icontains": q})
            qs = qs.filter(condition)
        for flt in self.get_filters():
            value = self.request.GET.get(flt.param, "")
            if value != "":
                qs = self.apply_filter(qs, flt, value)
        return qs.distinct() if self.search_fields else qs

    def apply_filter(self, qs, flt: ListFilter, value: str):
        return qs.filter(**{flt.lookup or flt.param: value})

    def get_template_names(self):
        names = super().get_template_names()
        if is_htmx(self.request):
            return [f"{names[0]}#results"]
        return names

    def get_create_url(self) -> str | None:
        from django.urls import reverse

        if not self.create_url_name:
            return None
        if self.create_caps and not self.request.user.has_cap(*self.create_caps):
            return None
        return reverse(self.create_url_name)

    def get_header_actions(self) -> list[Action]:
        return []

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        filters = self.get_filters()
        for flt in filters:
            flt.current = self.request.GET.get(flt.param, "")
        ctx.update(
            title=self.title,
            subtitle=self.subtitle,
            columns=self.columns,
            filters=filters,
            search_enabled=bool(self.search_fields),
            search_placeholder=self.search_placeholder,
            create_url=self.get_create_url(),
            create_label=self.create_label,
            header_actions=self.get_header_actions(),
            empty_message=self.empty_message,
        )
        return ctx


class FormContextMixin:
    title = ""
    intro = ""
    submit_label = "Save"
    success_message = "Saved."

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get_cancel_url(self) -> str:
        obj = getattr(self, "object", None)
        if obj is not None and getattr(obj, "pk", None):
            return obj.get_absolute_url()
        return safe_next_url(self.request) or "/"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            title=self.title,
            intro=self.intro,
            submit_label=self.submit_label,
            cancel_url=self.get_cancel_url(),
        )
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.success_message:
            messages.success(self.request, self.success_message)
        return response


class GenericCreateView(CapabilityRequiredMixin, FormContextMixin, CreateView):
    template_name = "crud/form.html"


class GenericUpdateView(
    CapabilityRequiredMixin,
    ScopedQuerysetMixin,
    ObjectPermissionMixin,
    FormContextMixin,
    UpdateView,
):
    template_name = "crud/form.html"
    require_edit = True


class GenericDetailView(
    CapabilityRequiredMixin, ScopedQuerysetMixin, ObjectPermissionMixin, DetailView
):
    template_name = "crud/detail.html"
    log_view = True

    def get_detail_sections(self) -> list[tuple[str, list[tuple[str, Any]]]]:
        return []

    def get_actions(self) -> list[Action]:
        return []

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["sections"] = self.get_detail_sections()
        ctx["actions"] = self.get_actions()
        return ctx
