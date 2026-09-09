from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from operations.models import OutboundMessage
from operations.tasks import deliver_message


class Command(BaseCommand):
    help = "Deliver queued messages through the local file/console backend only."

    def handle(self, **options):
        if settings.EMAIL_BACKEND not in [
            "django.core.mail.backends.filebased.EmailBackend",
            "django.core.mail.backends.console.EmailBackend",
            "django.core.mail.backends.locmem.EmailBackend",
        ]:
            raise CommandError("Use configured production Celery workers for external delivery.")
        results = [
            deliver_message(str(pk))
            for pk in OutboundMessage.objects.filter(sent_at__isnull=True).values_list("pk", flat=True)
        ]
        self.stdout.write(f"Outbox: {results.count('sent')} delivered locally; {results.count('failed')} failed.")
