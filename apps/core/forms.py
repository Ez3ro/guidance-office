from __future__ import annotations

from django import forms


class BootstrapFormMixin:
    """Adds Bootstrap classes and native date/time pickers to every widget.

    Forms may define `fieldsets = [("Title", ["field", ...]), ...]` to group fields.
    """

    filterable_select_threshold = 15

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxSelectMultiple | forms.RadioSelect):
                widget.attrs.setdefault("class", "form-check-input")
                continue
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
                continue
            if isinstance(widget, forms.DateTimeInput):
                widget.input_type = "datetime-local"
                widget.format = "%Y-%m-%dT%H:%M"
            elif isinstance(widget, forms.DateInput):
                widget.input_type = "date"
                widget.format = "%Y-%m-%d"
            elif isinstance(widget, forms.TimeInput):
                widget.input_type = "time"
                widget.format = "%H:%M"
            if isinstance(widget, forms.Select | forms.SelectMultiple):
                widget.attrs.setdefault("class", "form-select")
                queryset = getattr(field, "queryset", None)
                # Learner and staff lists get long; give them a type-to-filter box.
                if queryset is not None and queryset.model._meta.model_name in {"student", "user"}:
                    widget.attrs.setdefault("data-filterable", "true")
            else:
                widget.attrs.setdefault("class", "form-control")
            if isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("rows", 4)

    def checkbox_groups(self, name: str):
        """Groups a checkbox list's options using `checkbox_grouping = {field: fn(value) -> label}`."""
        grouper = getattr(self, "checkbox_grouping", {}).get(name)
        if grouper is None:
            return None
        groups: dict[str, list] = {}
        for option in self[name]:
            value = option.data["value"]
            groups.setdefault(grouper(getattr(value, "value", value)), []).append(option)
        return list(groups.items())

    def grouped_fields(self):
        fieldsets = getattr(self, "fieldsets", None)
        if not fieldsets:
            return [(None, [self[name] for name in self.fields])]
        used: set[str] = set()
        groups = []
        for title, names in fieldsets:
            present = [name for name in names if name in self.fields]
            used.update(present)
            if present:
                groups.append((title, [self[name] for name in present]))
        leftovers = [self[name] for name in self.fields if name not in used]
        if leftovers:
            groups.append((None, leftovers))
        return groups


class UserAwareFormMixin:
    """Pops a `user` kwarg so forms can limit choices to what the user may see."""

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)


class BaseModelForm(UserAwareFormMixin, BootstrapFormMixin, forms.ModelForm):
    pass


class BaseForm(UserAwareFormMixin, BootstrapFormMixin, forms.Form):
    pass


class AttachmentForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField()
    description = forms.CharField(max_length=255, required=False)
