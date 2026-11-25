"""Application-level encryption for confidential text (Fernet: AES-128-CBC + HMAC-SHA256).

Values are stored as "enc1:<token>". FIELD_ENCRYPTION_KEYS holds one or more keys:
the first encrypts, all of them decrypt, so keys can be rotated without downtime
(add the new key first, run `manage.py rotate_encryption_keys`, then drop the old key).
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

PREFIX = "enc1:"


class DecryptionError(Exception):
    """Raised when stored ciphertext can't be decrypted with the configured keys."""


@lru_cache(maxsize=1)
def _fernet() -> MultiFernet:
    keys = getattr(settings, "FIELD_ENCRYPTION_KEYS", None)
    if not keys:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS is not configured.")
    try:
        return MultiFernet([Fernet(key.encode() if isinstance(key, str) else key) for key in keys])
    except (ValueError, TypeError) as exc:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS must contain valid Fernet keys.") from exc


def clear_key_cache() -> None:
    _fernet.cache_clear()


def is_encrypted(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


def encrypt_str(value: str) -> str:
    return PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_str(value: str) -> str:
    if not is_encrypted(value):
        return value  # plaintext written before encryption was enabled
    try:
        return _fernet().decrypt(value[len(PREFIX) :].encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise DecryptionError(
            "Could not decrypt a stored value. Check that FIELD_ENCRYPTION_KEYS still "
            "contains the key the data was encrypted with."
        ) from exc
