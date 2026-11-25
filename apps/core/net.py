from django.conf import settings


def get_client_ip(request) -> str | None:
    """Client IP, trusting a proxy header only when CLIENT_IP_HEADER is configured.

    On Vercel the edge sets X-Real-IP; elsewhere REMOTE_ADDR is used so a client
    can't spoof its address with a forwarded-for header.
    """
    header = getattr(settings, "CLIENT_IP_HEADER", "")
    if header:
        value = request.META.get(header, "")
        if value:
            return value.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
