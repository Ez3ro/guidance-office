from __future__ import annotations

from functools import wraps

from django.contrib.auth.mixins import AccessMixin
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .roles import Cap


class CapabilityRequiredMixin(AccessMixin):
    """Requires a signed-in user holding at least one of `required_caps`."""

    required_caps: tuple[Cap, ...] = ()

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.required_caps and not request.user.has_cap(*self.required_caps):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def require_cap(*caps: Cap):
    """Function-view equivalent of CapabilityRequiredMixin."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            if caps and not request.user.has_cap(*caps):
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


def ensure(condition: bool) -> None:
    if not condition:
        raise PermissionDenied
