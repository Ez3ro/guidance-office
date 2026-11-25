"""Makes the current request available to model code (audit trail, created_by/updated_by)."""

from __future__ import annotations

from contextvars import ContextVar

_current_request: ContextVar = ContextVar("current_request", default=None)


def get_current_request():
    return _current_request.get()


def get_current_user():
    request = _current_request.get()
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return user
    return None


class RequestContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)
