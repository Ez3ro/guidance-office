from django.core.management.base import BaseCommand

from apps.scheduling.services import send_reminder_digests


class Command(BaseCommand):
    help = (
        "Emails each user their overdue and soon-due follow-ups (Vercel Cron calls the same code)."
    )

    def handle(self, *args, **options):
        result = send_reminder_digests()
        self.stdout.write(self.style.SUCCESS(str(result)))
