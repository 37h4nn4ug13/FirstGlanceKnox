import json
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import NotificationPreference, PushSubscription, StaffInvitation, StaffProfile, User
from .permissions import is_admin


INVITATION_SALT = "firstglanceknox.staff-invitation.v1"


@transaction.atomic
def invite_staff(*, actor, email, display_name, roles):
    from .staff_services import lock_actor, audit

    actor = lock_actor(actor)
    if not is_admin(actor):
        raise PermissionDenied
    if not roles or set(roles) - {"Admin", "Salesperson", "Cleaner"}:
        raise ValidationError("Choose at least one valid staff role.")
    email = email.strip().lower()
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError(
            "This email already has an account. Find the employee in Staff to update access or send a new invitation."
        )
    user = User.objects.create_user(email=email, password=None, is_active=False)
    for name in roles:
        group, _ = Group.objects.get_or_create(name=name)
        user.groups.add(group)
    StaffProfile.objects.create(user=user, display_name=display_name, onboarding_state="invited")
    invitation = StaffInvitation.objects.create(
        user=user, created_by=actor, expires_at=timezone.now() + timedelta(days=3)
    )
    audit(actor, "staff.invited", user, roles=sorted(roles))
    return invitation


def invitation_token(invitation):
    return signing.dumps({"id": str(invitation.public_id)}, salt=INVITATION_SALT)


def invitation_from_token(token):
    data = signing.loads(token, salt=INVITATION_SALT, max_age=3 * 24 * 3600)
    invitation = StaffInvitation.objects.select_related("user").get(public_id=data["id"])
    if invitation.revoked_at or invitation.accepted_at or invitation.expires_at <= timezone.now():
        raise signing.BadSignature("This invitation is no longer available.")
    return invitation


@transaction.atomic
def accept_invitation(*, token, password):
    from operations.services import _schedule_lock

    _schedule_lock()
    invitation = invitation_from_token(token)
    invitation = StaffInvitation.objects.select_for_update().get(pk=invitation.pk)
    if invitation.accepted_at or invitation.revoked_at or invitation.expires_at <= timezone.now():
        raise ValidationError("This invitation is no longer available.")
    user = invitation.user
    user.set_password(password)
    user.is_active = True
    user.save(update_fields=["password", "is_active"])
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["accepted_at"])
    StaffProfile.objects.filter(user=user).update(onboarding_state="active", is_active=True)
    return user


def email_invitation(invitation, request):
    link = request.build_absolute_uri(reverse("accounts:accept_invitation", args=[invitation_token(invitation)]))
    send_mail(
        "Your FirstGlanceKnox crew invitation",
        f"You're invited to join the FirstGlanceKnox crew.\n\nSet your password: {link}\n\nThis invitation expires in 3 days and can be used once.",
        settings.DEFAULT_FROM_EMAIL,
        [invitation.user.email],
    )


def push_configuration():
    return {
        "enabled": bool(getattr(settings, "PUSH_ENABLED", False) and getattr(settings, "VAPID_PUBLIC_KEY", "")),
        "public_key": getattr(settings, "VAPID_PUBLIC_KEY", ""),
    }


def validate_push_endpoint(endpoint):
    """Only known browser push services are permitted; never send to arbitrary URLs."""
    parsed = urlparse(endpoint)
    allowed = (
        "fcm.googleapis.com",
        "updates.push.services.mozilla.com",
        "push.services.mozilla.com",
        "web.push.apple.com",
        "wns.windows.com",
        "notify.windows.com",
    )
    if (
        parsed.scheme != "https"
        or parsed.port not in (None, 443)
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValidationError("Invalid push endpoint.")
    host = parsed.hostname or ""
    if not any(host == item or host.endswith("." + item) for item in allowed):
        raise ValidationError("This browser's push service is not supported.")


def send_safe_push(notification):
    """Opt-in fanout. Notification remains authoritative when push is disabled/unavailable."""
    if not getattr(settings, "PUSH_ENABLED", False):
        return 0
    key = getattr(settings, "VAPID_PRIVATE_KEY", "")
    if not key:
        return 0
    recipient = notification.recipient
    preference = NotificationPreference.objects.filter(user=recipient, push_enabled=True).first()
    if not preference or not recipient.is_active:
        return 0
    from pywebpush import WebPushException, webpush

    sent = 0
    for subscription in PushSubscription.objects.filter(user=recipient, active=True):
        validate_push_endpoint(subscription.endpoint)
        try:
            webpush(
                subscription_info={
                    "endpoint": subscription.endpoint,
                    "keys": {"p256dh": subscription.p256dh, "auth": subscription.auth},
                },
                data=json.dumps(
                    {
                        "title": "FirstGlanceKnox",
                        "body": "You have a new crew update. Open the app to view it.",
                        "url": "/crew/notifications/",
                    }
                ),
                vapid_private_key=key,
                vapid_claims={"sub": getattr(settings, "VAPID_SUBJECT", "mailto:admin@example.invalid")},
                timeout=10,
            )
            sent += 1
        except WebPushException as exc:
            if exc.response is not None and exc.response.status_code in (404, 410):
                subscription.active = False
                subscription.save(update_fields=["active"])
    return sent
