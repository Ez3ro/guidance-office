from django.core.signals import setting_changed
from django.dispatch import receiver

from .crypto import clear_key_cache


@receiver(setting_changed)
def reset_encryption_keys(sender, setting, **kwargs):
    if setting == "FIELD_ENCRYPTION_KEYS":
        clear_key_cache()
