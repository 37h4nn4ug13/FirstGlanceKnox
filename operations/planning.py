from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from . import services
from .models import AvailabilityBlock, Job, JobOffer, RecurringPlan


@transaction.atomic
def save_block(*, actor, values, block=None):
    services.require_admin(actor)
    services._schedule_lock()
    block = AvailabilityBlock.objects.select_for_update().get(pk=block.pk) if block else AvailabilityBlock()
    for name in ["staff", "starts_at", "ends_at", "reason"]:
        setattr(block, name, values[name])
    block.full_clean()
    if block.staff and not services.has_role(block.staff, "Admin", "Salesperson", "Cleaner"):
        raise ValidationError("Choose an active employee.")
    if block.staff:
        conflict = (
            JobOffer.objects.filter(
                cleaner=block.staff,
                status="accepted",
                job__scheduled_start__lt=block.ends_at,
                job__scheduled_end__gt=block.starts_at,
            )
            .exclude(job__status__in=["canceled", "completed"])
            .exists()
        )
    else:
        conflict = (
            Job.objects.filter(scheduled_start__lt=block.ends_at, scheduled_end__gt=block.starts_at)
            .exclude(status__in=["canceled", "completed"])
            .exists()
        )
    if conflict:
        raise ValidationError(
            "This block overlaps a booked appointment or accepted assignment. Reschedule that work first."
        )
    block.save()
    services._audit(
        actor,
        "availability.saved",
        block,
        start=block.starts_at.isoformat(),
        end=block.ends_at.isoformat(),
        reason=block.reason,
    )
    return block


@transaction.atomic
def remove_block(*, actor, block, reason):
    services.require_admin(actor)
    services._schedule_lock()
    block = AvailabilityBlock.objects.select_for_update().get(pk=block.pk)
    if not reason.strip():
        raise ValidationError("Explain why this unavailable time is being removed.")
    services._audit(
        actor,
        "availability.removed",
        block,
        reason=reason,
        start=block.starts_at.isoformat(),
        end=block.ends_at.isoformat(),
    )
    block.delete()


@transaction.atomic
def save_plan(*, actor, plan, values):
    services.require_admin(actor)
    services._schedule_lock()
    if not plan._state.adding:
        plan = RecurringPlan.objects.select_for_update().get(pk=plan.pk)
    if (
        plan.estimate.status != "accepted"
        or plan.property.customer_id != plan.customer_id
        or plan.estimate.property_id != plan.property_id
    ):
        raise ValidationError("Use the accepted estimate for this customer and property.")
    for name in ["name", "interval_days", "duration_minutes", "next_visit_at", "purchase_order", "active"]:
        if name in values:
            setattr(plan, name, values[name])
    plan.full_clean()
    if plan.active and plan.next_visit_at <= timezone.now():
        raise ValidationError("Choose a future next visit before activating this plan.")
    plan.save()
    services._audit(actor, "recurring_plan.saved", plan, active=plan.active, next_visit=plan.next_visit_at.isoformat())
    return plan
