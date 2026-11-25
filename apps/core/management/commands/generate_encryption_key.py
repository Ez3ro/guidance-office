from cryptography.fernet import Fernet
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Prints a new key for FIELD_ENCRYPTION_KEYS."

    def handle(self, *args, **options):
        self.stdout.write(Fernet.generate_key().decode())
        self.stderr.write(
            "Store this key in a password manager as well as in Vercel. "
            "Without it, encrypted records can't be read."
        )
