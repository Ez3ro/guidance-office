from django.conf import settings
from django.utils.functional import SimpleLazyObject

from .models import SchoolProfile
from .roles import Cap


def app_context(request):
    user = getattr(request, "user", None)
    caps = user.capabilities if user is not None and user.is_authenticated else frozenset()
    return {
        "SITE_NAME": settings.SITE_NAME,
        "school": SimpleLazyObject(SchoolProfile.load),
        "caps": {cap.value: cap in caps for cap in Cap},
    }
