from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.utils import timezone
from django.utils.html import escape
from .models import OutboundMessage


@shared_task
def deliver_message(message_id):
    """Persistent outbox + row lock prevents simultaneous delivery of the same intent."""
    with transaction.atomic():
        message = OutboundMessage.objects.select_for_update().get(pk=message_id)
        if message.sent_at:
            return "already_sent"
        parts = message.dedupe_key.split(":")
        if parts[0] == "estimate" and len(parts) > 2:
            from .models import Estimate

            document = Estimate.objects.filter(pk=parts[1]).first()
            if (
                not document
                or document.status not in ["sent", "viewed"]
                or parts[2] != f"v{document.public_token_version}"
            ):
                message.last_error = "Document no longer open or its links were revoked"
                message.attempts = max(message.attempts, 5)
                message.save(update_fields=["attempts", "last_error"])
                return "obsolete"
        message.attempts += 1
        try:
            mail = EmailMultiAlternatives(
                message.subject, message.body, settings.DEFAULT_FROM_EMAIL, [message.recipient]
            )
            mail.attach_alternative(
                f'<div style="font:16px/1.6 Arial;color:#293237"><h2 style="color:#1f7198">FirstGlanceKnox</h2><p>{escape(message.body).replace(chr(10), "<br>")}</p></div>',
                "text/html",
            )
            parts = message.dedupe_key.split(":")
            if parts[0] in ["invoice", "estimate"] and len(parts) > 1:
                from .models import Estimate, Invoice
                from portal.services import document_pdf

                model = Invoice if parts[0] == "invoice" else Estimate
                document = model.objects.filter(pk=parts[1]).first()
                if document:
                    mail.attach(f"{document.number}.pdf", document_pdf(document, kind=parts[0]), "application/pdf")
            mail.send(fail_silently=False)
        except Exception as exc:
            # Store exception class only: providers may include addresses or tokens in error strings.
            message.last_error = type(exc).__name__
            message.save(update_fields=["attempts", "last_error"])
            return "failed"
        message.sent_at = timezone.now()
        message.last_error = ""
        message.save(update_fields=["sent_at", "attempts", "last_error"])
        return "sent"


@shared_task
def fanout_notification(notification_id):
    from accounts.services import send_safe_push
    from .models import Notification

    note = Notification.objects.get(pk=notification_id)
    return send_safe_push(note)


@shared_task
def maintenance():
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from . import services
    from .models import JobOffer, Lead, RecurringPlan

    now = timezone.now()
    for message_id in OutboundMessage.objects.filter(sent_at__isnull=True, attempts__lt=5).values_list("pk", flat=True)[
        :100
    ]:
        deliver_message(str(message_id))
    with transaction.atomic():
        for offer in JobOffer.objects.select_for_update().filter(status="offered", expires_at__lte=now):
            offer.status = "expired"
            offer.save(update_fields=["status"])
            services._refresh_assignment_status(offer.job)
            services._audit(None, "offer.expired", offer)
            services.notify_admins("offer.expired", "A job offer expired without a response", offer)
    for lead in Lead.objects.filter(follow_up_at__lte=now, assigned_to__isnull=False).exclude(
        status__in=["won", "lost", "do_not_contact"]
    ):
        services.notify(
            recipient=lead.assigned_to,
            kind="lead.follow_up",
            title="A follow-up is due",
            link=f"/crew/leads/{lead.pk}/",
            obj=lead,
            dedupe_key=f"followup:{lead.pk}:{lead.follow_up_at.isoformat()}",
        )
    admin = get_user_model().objects.filter(Q(is_superuser=True) | Q(groups__name="Admin"), is_active=True).first()
    if admin:
        for plan in RecurringPlan.objects.filter(
            active=True, next_visit_at__gte=now, next_visit_at__lte=now + timezone.timedelta(days=30)
        )[:100]:
            try:
                services.generate_recurring_visit(actor=admin, plan=plan)
            except Exception as exc:
                from django.core.exceptions import ValidationError

                if not isinstance(exc, ValidationError):
                    raise
                services.notify_admins(
                    "schedule.conflict",
                    "A recurring visit needs scheduling review",
                    plan,
                    suffix=now.date().isoformat(),
                )
    return "complete"
