from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.fields import EncryptedTextField


class Command(BaseCommand):
    help = (
        "Re-encrypts every encrypted field with the first key in FIELD_ENCRYPTION_KEYS. "
        "To rotate: put the new key first (keep the old one after it), deploy, run this, "
        "then remove the old key."
    )

    def handle(self, *args, **options):
        total = 0
        for model in apps.get_models():
            fields = [
                f.name for f in model._meta.concrete_fields if isinstance(f, EncryptedTextField)
            ]
            if not fields:
                continue
            count = 0
            with transaction.atomic():
                for obj in model._base_manager.all().iterator(chunk_size=200):
                    # Values load decrypted; writing them back re-encrypts with the primary key.
                    # update() skips save() so timestamps and the audit trail stay untouched.
                    model._base_manager.filter(pk=obj.pk).update(
                        **{name: getattr(obj, name) for name in fields}
                    )
                    count += 1
            total += count
            self.stdout.write(f"{model._meta.label}: {count} row(s) re-encrypted")
        self.stdout.write(self.style.SUCCESS(f"Done. {total} row(s) re-encrypted."))
