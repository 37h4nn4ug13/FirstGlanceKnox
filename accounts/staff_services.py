"""Staff lifecycle operations; retain operational history and revoke access safely."""

from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from operations import services as domain
from operations.models import AuditEvent, JobOffer, Lead
from .models import PushSubscription, StaffInvitation, StaffProfile, User

ROLES = {"Admin", "Salesperson", "Cleaner"}


def lock_actor(actor):
    domain._schedule_lock()
    actor = User.objects.select_for_update().get(pk=actor.pk)
    domain.require_admin(actor)
    return actor


def audit(actor, action, user, **details):
    AuditEvent.objects.create(
        actor=actor, action=action, object_type="accounts.user", object_id=user.public_id, details=details
    )


def handoff(user, *, remove_sales=False, remove_cleaner=False, actor):
    if remove_sales:
        leads = Lead.objects.filter(assigned_to=user).exclude(status__in=["won", "lost", "do_not_contact"])
        for lead in leads:
            lead.assigned_to = None
            lead.save(update_fields=["assigned_to", "updated_at"])
            domain._audit(actor, "lead.unassigned", lead, reason="Staff access changed")
    if remove_cleaner:
        for offer in JobOffer.objects.filter(cleaner=user, status__in=["offered", "accepted"]).select_related("job"):
            if offer.job.status in ["scheduled", "offered", "confirmed"]:
                domain.withdraw_offer(actor=actor, offer=offer, reason="Staff access changed; reassignment required")
            else:
                # Never silently cancel work in progress or reverse its compensation.
                domain.notify_admins(
                    "staff.handoff",
                    "An active job needs staff handoff",
                    offer.job,
                    suffix=str(timezone.now().timestamp()),
                )


@transaction.atomic
def update_staff(
    *, actor, user, roles, display_name, phone="", skills="", internal_notes="", default_commission_rate=0
):
    actor = lock_actor(actor)
    user = User.objects.select_for_update().get(pk=user.pk)
    if not roles or set(roles) - ROLES:
        raise ValidationError("Choose at least one supported staff role.")
    if user.is_superuser and (not actor.is_superuser or "Admin" not in roles):
        raise PermissionDenied(
            "Owner access is protected. An owner can maintain this profile with the Admin role retained."
        )
    if user.pk == actor.pk and "Admin" not in roles:
        raise ValidationError("You cannot remove your own administrator access.")
    previous = set(user.groups.values_list("name", flat=True)) & ROLES
    profile = StaffProfile.objects.select_for_update().get(user=user)
    before_rate = str(profile.default_commission_rate)
    profile.display_name, profile.phone, profile.skills = display_name, phone, skills
    profile.internal_notes, profile.default_commission_rate = internal_notes, default_commission_rate
    profile.full_clean()
    profile.save()
    handoff(
        user,
        actor=actor,
        remove_sales="Salesperson" in previous and "Salesperson" not in roles,
        remove_cleaner="Cleaner" in previous and "Cleaner" not in roles,
    )
    user.groups.remove(*Group.objects.filter(name__in=ROLES))
    user.groups.add(*(Group.objects.get_or_create(name=role)[0] for role in roles))
    if "Admin" not in roles:
        user.is_staff = False
        user.user_permissions.clear()
        user.save(update_fields=["is_staff"])
    audit(
        actor,
        "staff.updated",
        user,
        previous_roles=sorted(previous),
        roles=sorted(roles),
        previous_commission=before_rate,
        commission=str(profile.default_commission_rate),
    )
    return user


@transaction.atomic
def deactivate_staff(*, actor, user, reason):
    actor = lock_actor(actor)
    user = User.objects.select_for_update().get(pk=user.pk)
    if user.pk == actor.pk or user.is_superuser:
        raise ValidationError("Your own account and protected owner accounts cannot be deactivated here.")
    if not reason.strip():
        raise ValidationError("Enter a reason for deactivating access.")
    profile = StaffProfile.objects.select_for_update().get(user=user)
    if profile.onboarding_state == "inactive":
        raise ValidationError("This employee is already inactive.")
    handoff(user, actor=actor, remove_sales=True, remove_cleaner=True)
    user.is_active = user.is_staff = False
    # Invalidates all existing session authentication hashes, including after rehire.
    user.set_unusable_password()
    user.save(update_fields=["is_active", "is_staff", "password"])
    profile.is_active, profile.onboarding_state = False, "inactive"
    profile.save(update_fields=["is_active", "onboarding_state"])
    user.invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
    PushSubscription.objects.filter(user=user).update(active=False)
    audit(actor, "staff.deactivated", user, reason=reason)


@transaction.atomic
def renew_invitation(*, actor, user):
    actor = lock_actor(actor)
    user = User.objects.select_for_update().get(pk=user.pk)
    profile = StaffProfile.objects.select_for_update().get(user=user)
    if user.is_active or user.is_superuser:
        raise ValidationError(
            "Active employees should use password recovery; only invited or inactive employees can be invited again."
        )
    if not user.groups.filter(name__in=ROLES).exists():
        raise ValidationError("Choose employee roles before inviting them.")
    user.invitations.filter(accepted_at__isnull=True, revoked_at__isnull=True).update(revoked_at=timezone.now())
    invitation = StaffInvitation.objects.create(
        user=user, created_by=actor, expires_at=timezone.now() + timezone.timedelta(days=3)
    )
    profile.onboarding_state = "invited"
    profile.save(update_fields=["onboarding_state"])
    audit(actor, "staff.reinvited", user)
    return invitation


@transaction.atomic
def revoke_invitation(*, actor, invitation):
    actor = lock_actor(actor)
    invitation = StaffInvitation.objects.select_for_update().get(pk=invitation.pk)
    if invitation.accepted_at or invitation.revoked_at:
        raise ValidationError("This invitation is no longer open.")
    invitation.revoked_at = timezone.now()
    invitation.save(update_fields=["revoked_at"])
    audit(actor, "staff.invitation_revoked", invitation.user)
