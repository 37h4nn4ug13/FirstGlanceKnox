"""Authoritative state transitions. Views, admin actions, and workers call here.

Amounts are USD Decimal. Commission earns on full payment; cleaner pay becomes
payable on approved completion. PostgreSQL is required for concurrent production
writes: a singleton row serializes resource reservations and invoice numbering.
"""

import hashlib
import re
import secrets
from datetime import timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import (
    AccessToken,
    AuditEvent,
    AvailabilityBlock,
    CleanerPayout,
    CommissionEntry,
    Contact,
    Customer,
    Estimate,
    EstimateLine,
    Invoice,
    InvoiceLine,
    InvoiceSequence,
    Job,
    JobOffer,
    Lead,
    LeadVisit,
    Notification,
    OutboundMessage,
    Payment,
    PriceBookItem,
    Property,
    RecurringPlan,
    ScheduleLock,
)


CENT = Decimal("0.01")


def money(value):
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            raise InvalidOperation
        amount = amount.quantize(CENT, rounding=ROUND_HALF_UP)
        if abs(amount) > Decimal("9999999999.99"):
            raise InvalidOperation
        return amount
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Enter a valid monetary amount.") from None


def has_role(user, *roles):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, "staff_profile", None)
    if profile and not profile.is_active:
        return False
    return user.groups.filter(name__in=roles).exists()


def is_admin(user):
    return has_role(user, "Admin")


def require_admin(user):
    if not is_admin(user):
        raise PermissionDenied("An administrator must perform this action.")


def require_sales(user):
    if not has_role(user, "Admin", "Salesperson"):
        raise PermissionDenied("Sales access is required.")


def leads_for(user):
    queryset = Lead.objects.select_related("customer", "property", "assigned_to", "created_by")
    if is_admin(user):
        return queryset
    if has_role(user, "Salesperson"):
        return queryset.filter(Q(assigned_to=user) | Q(created_by=user))
    return queryset.none()


def estimates_for(user):
    queryset = Estimate.objects.select_related("customer", "property", "salesperson", "lead")
    if is_admin(user):
        return queryset
    if has_role(user, "Salesperson"):
        return queryset.filter(Q(salesperson=user) | Q(lead__assigned_to=user) | Q(lead__created_by=user)).distinct()
    if user and user.is_authenticated and user.is_active:
        return queryset.filter(customer__user=user).exclude(status__in=[Estimate.Status.DRAFT, Estimate.Status.REVIEW])
    return queryset.none()


def jobs_for(user):
    queryset = Job.objects.select_related("customer", "property", "estimate", "salesperson")
    if is_admin(user):
        return queryset
    scope = Q(pk__in=[])
    if has_role(user, "Salesperson"):
        scope |= Q(salesperson=user)
    if has_role(user, "Cleaner"):
        scope |= Q(offers__cleaner=user, offers__status__in=["offered", "accepted", "completed"])
    if user and user.is_authenticated and user.is_active:
        scope |= Q(customer__user=user)
    return queryset.filter(scope).distinct()


def invoices_for(user):
    queryset = Invoice.objects.select_related("customer", "job", "job__property")
    if is_admin(user):
        return queryset
    if user and user.is_authenticated and user.is_active:
        # Staff sales status is exposed through their commission ledger, not
        # through company/customer billing records.
        return queryset.filter(customer__user=user).exclude(status="draft")
    return queryset.none()


def customers_for(user):
    queryset = Customer.objects.all()
    if is_admin(user):
        return queryset
    if has_role(user, "Salesperson"):
        return queryset.filter(Q(leads__assigned_to=user) | Q(leads__created_by=user)).distinct()
    if user and user.is_authenticated and user.is_active:
        return queryset.filter(user=user)
    return queryset.none()


def require_lead(user, lead):
    require_sales(user)
    if not leads_for(user).filter(pk=lead.pk).exists():
        raise PermissionDenied("This lead is not assigned to you.")


def _audit(actor, action, obj, **details):
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=obj._meta.label_lower,
        object_id=obj.pk,
        details=details,
    )


def notify(*, recipient, kind, title, body="", link="", obj=None, dedupe_key=None):
    if not recipient or not recipient.is_active:
        return None
    defaults = dict(kind=kind, title=title, body=body, link=link, object_id=getattr(obj, "pk", None))
    if dedupe_key:
        notification, created = Notification.objects.get_or_create(
            recipient=recipient, dedupe_key=dedupe_key, defaults=defaults
        )
    else:
        notification = Notification.objects.create(recipient=recipient, **defaults)
        created = True
    if created and getattr(settings, "NOTIFICATIONS_FANOUT_ENABLED", False):
        from .tasks import fanout_notification

        transaction.on_commit(lambda: fanout_notification.delay(str(notification.pk)))
    return notification


def notify_admins(kind, title, obj, suffix=""):
    users = get_user_model().objects.filter(Q(is_superuser=True) | Q(groups__name="Admin"), is_active=True).distinct()
    for user in users:
        notify(
            recipient=user,
            kind=kind,
            title=title,
            body="Open your workspace to review this update.",
            link="/crew/",
            obj=obj,
            dedupe_key=f"{kind}:{obj.pk}:{suffix}",
        )


def _normal_address(address, city, postal_code):
    return re.sub(r"\W+", " ", f"{address} {city} {postal_code}".casefold()).strip()[:320]


@transaction.atomic
def capture_lead(
    *,
    actor=None,
    name,
    address,
    email="",
    phone="",
    kind="residential",
    services=None,
    message="",
    preferred_date=None,
    source="website",
    follow_up_at=None,
    outcome="",
    city="Knoxville",
    state="TN",
    postal_code="",
    idempotency_key=None,
):
    if actor:
        require_sales(actor)
    else:
        source = "website"
    if not str(address).strip() or not str(name).strip():
        raise ValidationError("Name and service address are required.")
    if kind not in Customer.Kind.values:
        raise ValidationError("Choose a residential or commercial account.")
    email = email.strip().lower()
    phone = phone.strip()
    key = f"{actor.pk if actor else 'website'}:{idempotency_key}" if idempotency_key else None
    if key:
        existing = Lead.objects.filter(idempotency_key=key).first()
        if existing:
            if actor:
                require_lead(actor, existing)
            return existing
    # The shared lock prevents duplicate matching races with simultaneous forms.
    _schedule_lock()
    address_key = _normal_address(address, city, postal_code)
    properties = Property.objects.select_related("customer").filter(address_key=address_key)
    if properties.filter(customer__do_not_contact=True).exists():
        raise ValidationError("This address is marked do not contact. An administrator must review it.")
    contact_match = Q(pk__in=[])
    if email:
        contact_match |= Q(email__iexact=email)
    if phone:
        contact_match |= Q(phone=phone)
    customer = Customer.objects.filter(contact_match).first()
    if customer and customer.do_not_contact:
        raise ValidationError("This contact is marked do not contact. An administrator must review it.")
    if not customer:
        customer = Customer.objects.create(name=name.strip()[:180], email=email, phone=phone[:40], kind=kind)
        Contact.objects.create(
            customer=customer,
            name=customer.name,
            email=email,
            phone=phone[:40],
            is_primary=True,
            is_billing=True,
            is_site=True,
        )
    property_obj = properties.filter(customer=customer).first()
    if property_obj is None:
        property_obj = Property.objects.create(
            customer=customer,
            address_line1=address.strip()[:240],
            city=city,
            state=state,
            postal_code=postal_code,
            kind=kind,
            address_key=address_key,
        )
    lead = Lead.objects.create(
        customer=customer,
        property=property_obj,
        assigned_to=actor,
        created_by=actor,
        source=source[:40],
        services=services or [],
        notes=message,
        preferred_date=preferred_date,
        follow_up_at=follow_up_at,
        idempotency_key=key,
    )
    if outcome:
        record_visit(actor=actor, lead=lead, outcome=outcome, notes=message)
    _audit(actor, "lead.created", lead, source=source)
    notify_admins("lead.created", "A new quote request is ready", lead)
    return lead


create_lead = capture_lead


@transaction.atomic
def create_repeat_lead(*, actor, property, notes=""):
    if not actor.is_authenticated or property.customer.user_id != actor.pk:
        raise PermissionDenied
    lead = Lead.objects.create(
        customer=property.customer, property=property, source="repeat_customer", notes=str(notes)[:5000]
    )
    _audit(actor, "lead.repeat_requested", lead)
    notify_admins("lead.repeat_requested", "A customer requested repeat service", lead)
    return lead


@transaction.atomic
def record_visit(*, actor, lead, outcome, notes="", follow_up_at=None):
    require_lead(actor, lead)
    lead = Lead.objects.select_for_update().get(pk=lead.pk)
    if lead.customer.do_not_contact and outcome != "do_not_contact":
        raise ValidationError("This contact is marked do not contact.")
    visit = LeadVisit.objects.create(lead=lead, salesperson=actor, outcome=outcome[:40], notes=notes)
    if outcome == "do_not_contact":
        lead.status = Lead.Status.DO_NOT_CONTACT
        Customer.objects.filter(pk=lead.customer_id).update(do_not_contact=True)
    elif outcome in ["interested", "estimate_requested"]:
        lead.status = Lead.Status.QUALIFIED
    elif outcome in ["follow_up", "follow_up_later"]:
        lead.status = Lead.Status.FOLLOW_UP
    elif outcome == "not_interested":
        lead.status = Lead.Status.LOST
    if follow_up_at:
        lead.follow_up_at = follow_up_at
    lead.save(update_fields=["status", "follow_up_at", "updated_at"])
    _audit(actor, "lead.visit_recorded", lead, outcome=outcome)
    return visit


@transaction.atomic
def create_estimate(
    *,
    actor,
    lead,
    lines,
    discount=0,
    tax_rate=0,
    terms=None,
    expires_on=None,
    customer_notes="",
    supersedes=None,
    revision_reason="",
):
    require_lead(actor, lead)
    if supersedes:
        supersedes = Estimate.objects.select_for_update().get(pk=supersedes.pk)
        if supersedes.lead_id != lead.pk or supersedes.status in ["accepted", "superseded"]:
            raise ValidationError(
                "Only the current unaccepted estimate can be revised. Accepted terms remain unchanged."
            )
        if not revision_reason.strip():
            raise ValidationError("Explain the estimate revision.")
    lead = Lead.objects.select_for_update().select_related("customer", "property").get(pk=lead.pk)
    if lead.customer.do_not_contact or lead.status == Lead.Status.DO_NOT_CONTACT:
        raise ValidationError("This customer is marked do not contact.")
    if not lines:
        raise ValidationError("Add at least one service to the estimate.")
    discount, tax_rate = money(discount), money(tax_rate)
    if discount < 0 or not 0 <= tax_rate <= 100:
        raise ValidationError("Discount must be positive and tax percentage must be between 0 and 100.")
    requires_approval = lead.customer.kind == "commercial" or lead.property.stories > 2 or bool(lead.property.hazards)
    estimate = Estimate.objects.create(
        lead=lead,
        customer=lead.customer,
        property=lead.property,
        salesperson=lead.assigned_to or actor,
        discount=discount,
        tax_rate=tax_rate,
        expires_on=expires_on or timezone.localdate() + timedelta(days=30),
        customer_notes=customer_notes,
        supersedes=supersedes,
    )
    if terms is not None:
        estimate.terms = terms
    subtotal = Decimal("0.00")
    commissionable = Decimal("0.00")
    for position, raw in enumerate(lines):
        item = raw.get("price_book_item")
        if item is None and raw.get("item_id"):
            item = PriceBookItem.objects.get(pk=raw["item_id"], active=True)
        if item and not item.active:
            raise ValidationError("An inactive price-book service cannot be quoted.")
        quantity = money(raw.get("quantity", 1))
        price = money(raw.get("unit_price") if raw.get("unit_price") is not None else item.unit_price if item else 0)
        if quantity <= 0 or price < 0:
            raise ValidationError("Quantity must be greater than zero and price cannot be negative.")
        if not item or (item and price != item.unit_price):
            requires_approval = True
        if item and item.requires_approval:
            requires_approval = True
        description = raw.get("description") or (item.name if item else "")
        if not description.strip():
            raise ValidationError("Each line needs a description.")
        total = money(quantity * price)
        is_commissionable = item.commissionable if item else bool(raw.get("commissionable", True))
        EstimateLine.objects.create(
            estimate=estimate,
            price_book_item=item,
            description=description,
            quantity=quantity,
            unit=raw.get("unit") or (item.unit if item else "service"),
            unit_price=price,
            total=total,
            commissionable=is_commissionable,
            position=position,
        )
        subtotal += total
        if is_commissionable:
            commissionable += total
    if discount > subtotal:
        raise ValidationError("Discount cannot exceed the service subtotal.")
    discount_limit = Decimal(str(getattr(settings, "SALESPERSON_MAX_DISCOUNT_PERCENT", "10")))
    if subtotal and discount / subtotal * 100 > discount_limit:
        requires_approval = True
    if subtotal > Decimal(str(getattr(settings, "ESTIMATE_APPROVAL_THRESHOLD", "2000"))):
        requires_approval = True
    estimate.subtotal = money(subtotal)
    estimate.tax = money((subtotal - discount) * tax_rate / 100)
    estimate.total = money(subtotal - discount + estimate.tax)
    # Allocate the shared discount proportionally to commissionable services.
    estimate.commissionable_base = (
        money(commissionable * (subtotal - discount) / subtotal) if subtotal else Decimal("0.00")
    )
    estimate.status = Estimate.Status.REVIEW if requires_approval and not is_admin(actor) else Estimate.Status.DRAFT
    if is_admin(actor):
        estimate.approved_by = actor
    estimate.save()
    if supersedes:
        supersedes.status = Estimate.Status.SUPERSEDED
        supersedes.public_token_version += 1
        supersedes.save(update_fields=["status", "public_token_version", "updated_at"])
        AccessToken.objects.filter(object_id=supersedes.pk, purpose="estimate", revoked_at__isnull=True).update(
            revoked_at=timezone.now()
        )
        _audit(actor, "estimate.revised", supersedes, replacement=str(estimate.pk), reason=revision_reason)
    _audit(actor, "estimate.created", estimate, total=str(estimate.total))
    if estimate.status == Estimate.Status.REVIEW:
        notify_admins("estimate.review", "An estimate needs pricing approval", estimate)
    return estimate


@transaction.atomic
def approve_estimate(*, actor, estimate):
    require_admin(actor)
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Status.REVIEW:
        raise ValidationError("This estimate is not waiting for approval.")
    estimate.status, estimate.approved_by = Estimate.Status.DRAFT, actor
    estimate.save(update_fields=["status", "approved_by", "updated_at"])
    _audit(actor, "estimate.pricing_approved", estimate)
    return estimate


def _token_hash(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


@transaction.atomic
def create_access_token(*, actor, obj, purpose=None, lifetime_days=30):
    purpose = purpose or obj._meta.model_name
    if isinstance(obj, Estimate):
        require_lead(actor, obj.lead)
    elif isinstance(obj, Invoice):
        require_admin(actor)
    else:
        raise ValidationError("Unsupported secure link type.")
    if purpose != obj._meta.model_name:
        raise ValidationError("Secure link purpose does not match its object.")
    token = signing.dumps({"secret": secrets.token_urlsafe(32)}, salt="firstglance.document")
    AccessToken.objects.create(
        secret_hash=_token_hash(token),
        purpose=purpose,
        object_id=obj.pk,
        version=obj.public_token_version,
        expires_at=timezone.now() + timedelta(days=lifetime_days),
    )
    _audit(actor, "portal.link_created", obj, purpose=purpose)
    return token


def resolve_access_token(secret, purpose):
    if not isinstance(secret, str) or not 20 <= len(secret) <= 512:
        raise PermissionDenied("This secure link is invalid or no longer available.")
    try:
        signing.loads(secret, salt="firstglance.document", max_age=settings.PORTAL_TOKEN_MAX_AGE)
    except signing.BadSignature:
        raise PermissionDenied("This secure link is invalid or has expired.") from None
    record = AccessToken.objects.filter(
        secret_hash=_token_hash(secret), purpose=purpose, revoked_at__isnull=True, expires_at__gt=timezone.now()
    ).first()
    model = {"estimate": Estimate, "invoice": Invoice}.get(purpose)
    if not record or not model:
        raise PermissionDenied("This secure link is invalid or no longer available.")
    obj = model.objects.filter(pk=record.object_id, public_token_version=record.version).first()
    if not obj:
        raise PermissionDenied("This secure link is invalid or no longer available.")
    if isinstance(obj, Estimate) and obj.status in ["draft", "review", "superseded"]:
        raise PermissionDenied("This estimate is not available.")
    if isinstance(obj, Invoice) and obj.status == "draft":
        raise PermissionDenied("This invoice is not available.")
    return obj


@transaction.atomic
def revoke_access_tokens(*, actor, obj):
    require_admin(actor)
    obj = type(obj).objects.select_for_update().get(pk=obj.pk)
    obj.public_token_version += 1
    obj.save(update_fields=["public_token_version", "updated_at"])
    AccessToken.objects.filter(object_id=obj.pk, revoked_at__isnull=True).update(revoked_at=timezone.now())
    _audit(actor, "portal.links_revoked", obj)
    return obj


def _queue_message(*, key, customer, subject, body):
    if not customer.email:
        return None
    message, _ = OutboundMessage.objects.get_or_create(
        dedupe_key=key, defaults={"recipient": customer.email, "subject": subject, "body": body}
    )
    if getattr(settings, "EMAIL_TASKS_ENABLED", False):
        from .tasks import deliver_message

        transaction.on_commit(lambda: deliver_message.delay(str(message.pk)))
    return message


@transaction.atomic
def send_estimate(*, actor, estimate):
    require_lead(actor, estimate.lead)
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status not in [Estimate.Status.DRAFT, Estimate.Status.SENT, Estimate.Status.VIEWED]:
        raise ValidationError("This estimate must be approved before it can be sent.")
    if estimate.expires_on and estimate.expires_on < timezone.localdate():
        raise ValidationError("Create a revision with a current expiration date.")
    estimate.status = Estimate.Status.SENT
    estimate.sent_at = timezone.now()
    estimate.save(update_fields=["status", "sent_at", "updated_at"])
    token = create_access_token(actor=actor, obj=estimate)
    Lead.objects.filter(pk=estimate.lead_id).update(status=Lead.Status.ESTIMATE_SENT)
    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    _queue_message(
        key=f"estimate:{estimate.pk}:v{estimate.public_token_version}",
        customer=estimate.customer,
        subject=f"Your FirstGlanceKnox estimate {estimate.number}",
        body=f"Your estimate is ready to review securely:\n{site_url}/portal/estimate/{token}/\n\nTotal: ${estimate.total}\n\nFirstGlanceKnox",
    )
    _audit(actor, "estimate.sent", estimate)
    return token


def _authorize_customer_decision(actor, estimate, token):
    if token:
        resolved = resolve_access_token(token, "estimate")
        if resolved.pk == estimate.pk:
            return
    if (
        actor
        and actor.is_authenticated
        and actor.is_active
        and (is_admin(actor) or estimate.customer.user_id == actor.pk)
    ):
        return
    raise PermissionDenied("Customer approval requires an authorized customer or a valid secure link.")


@transaction.atomic
def accept_estimate(*, actor=None, estimate, signature, token=None):
    estimate = Estimate.objects.select_for_update().select_related("salesperson", "customer").get(pk=estimate.pk)
    _authorize_customer_decision(actor, estimate, token)
    if estimate.status not in [Estimate.Status.SENT, Estimate.Status.VIEWED]:
        raise ValidationError("This estimate is no longer open for acceptance.")
    if estimate.expires_on and estimate.expires_on < timezone.localdate():
        raise ValidationError("This estimate has expired. Please request an updated estimate.")
    if not str(signature).strip():
        raise ValidationError("Enter your name to confirm acceptance.")
    profile = getattr(estimate.salesperson, "staff_profile", None)
    estimate.commission_rate_snapshot = money(profile.default_commission_rate if profile else 0)
    if not 0 <= estimate.commission_rate_snapshot <= 100:
        raise ValidationError("The salesperson commission configuration needs admin review.")
    estimate.status, estimate.accepted_at = Estimate.Status.ACCEPTED, timezone.now()
    estimate.accepted_by = str(signature).strip()[:180]
    estimate.accepted_snapshot = {
        "number": estimate.number,
        "customer_id": str(estimate.customer_id),
        "customer_name": estimate.customer.name,
        "property_id": str(estimate.property_id),
        "address": estimate.property.address,
        "salesperson_id": str(estimate.salesperson_id) if estimate.salesperson_id else None,
        "commission_rate": str(estimate.commission_rate_snapshot),
        "commissionable_base": str(estimate.commissionable_base),
        "subtotal": str(estimate.subtotal),
        "discount": str(estimate.discount),
        "tax_rate": str(estimate.tax_rate),
        "tax": str(estimate.tax),
        "total": str(estimate.total),
        "terms": estimate.terms,
        "customer_notes": estimate.customer_notes,
        "accepted_by": estimate.accepted_by,
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit": line.unit,
                "unit_price": str(line.unit_price),
                "total": str(line.total),
                "commissionable": line.commissionable,
            }
            for line in estimate.lines.all()
        ],
    }
    estimate.save(
        update_fields=[
            "commission_rate_snapshot",
            "status",
            "accepted_at",
            "accepted_by",
            "accepted_snapshot",
            "updated_at",
        ]
    )
    if token:
        AccessToken.objects.filter(secret_hash=_token_hash(token)).update(used_at=timezone.now())
    _audit(actor, "estimate.accepted", estimate, signature=estimate.accepted_by)
    notify(
        recipient=estimate.salesperson,
        kind="estimate.accepted",
        title="Your estimate was accepted",
        link=f"/crew/estimates/{estimate.pk}/",
        obj=estimate,
        dedupe_key=f"estimate.accepted:{estimate.pk}",
    )
    notify_admins("estimate.accepted", "An accepted estimate is ready to schedule", estimate)
    return estimate


@transaction.atomic
def decline_estimate(*, actor=None, estimate, reason="", token=None):
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    _authorize_customer_decision(actor, estimate, token)
    if estimate.status not in [Estimate.Status.SENT, Estimate.Status.VIEWED]:
        raise ValidationError("This estimate is no longer open for a response.")
    estimate.status = Estimate.Status.DECLINED
    estimate.save(update_fields=["status", "updated_at"])
    _audit(actor, "estimate.declined", estimate, reason=reason)
    notify(
        recipient=estimate.salesperson,
        kind="estimate.declined",
        title="An estimate was declined",
        link="/crew/estimates/",
        obj=estimate,
        dedupe_key=f"estimate.declined:{estimate.pk}",
    )
    return estimate


def _schedule_lock():
    ScheduleLock.objects.get_or_create(pk=1)
    return ScheduleLock.objects.select_for_update().get(pk=1)


def _validate_window(start, end):
    if timezone.is_naive(start) or timezone.is_naive(end):
        raise ValidationError("Scheduling requires timezone-aware dates and times.")
    if end <= start:
        raise ValidationError("The end time must be after the start time.")
    if end - start > timedelta(hours=16):
        raise ValidationError("Schedule each service visit within a 16-hour window.")


def _check_booking(start, end, exclude_job=None):
    buffer_minutes = int(getattr(settings, "SCHEDULE_BUFFER_MINUTES", 30))
    buffered_start, buffered_end = start - timedelta(minutes=buffer_minutes), end + timedelta(minutes=buffer_minutes)
    if AvailabilityBlock.objects.filter(
        staff__isnull=True, starts_at__lt=buffered_end, ends_at__gt=buffered_start
    ).exists():
        raise ValidationError("This time is blocked. Choose another appointment.")
    conflicts = Job.objects.exclude(status=Job.Status.CANCELED).filter(
        scheduled_start__lt=buffered_end, scheduled_end__gt=buffered_start
    )
    if exclude_job:
        conflicts = conflicts.exclude(pk=exclude_job.pk)
    if conflicts.count() >= int(getattr(settings, "SCHEDULE_CAPACITY", 1)):
        raise ValidationError("This appointment conflicts with another booking. Choose another time.")


def available_slots(*, actor, starts_at, ends_at, duration_minutes=120):
    require_sales(actor)
    _validate_window(starts_at, ends_at)
    result, current = [], starts_at
    while current + timedelta(minutes=duration_minutes) <= ends_at:
        finish = current + timedelta(minutes=duration_minutes)
        try:
            _check_booking(current, finish)
            result.append({"start": current, "end": finish})
        except ValidationError:
            pass
        current += timedelta(minutes=30)
    return result


@transaction.atomic
def schedule_job(
    *,
    actor,
    estimate,
    scheduled_start,
    scheduled_end,
    scope=None,
    checklist=None,
    recurring_plan=None,
    recurrence_key=None,
):
    require_lead(actor, estimate.lead)
    _schedule_lock()
    estimate = Estimate.objects.select_for_update().get(pk=estimate.pk)
    if estimate.status != Estimate.Status.ACCEPTED or not estimate.accepted_snapshot:
        raise ValidationError("A customer-approved estimate is required before booking.")
    _validate_window(scheduled_start, scheduled_end)
    if scheduled_start < timezone.now():
        raise ValidationError("Choose a future service appointment.")
    if not recurring_plan and Job.objects.filter(estimate=estimate).exclude(status="canceled").exists():
        raise ValidationError("This estimate already has a booked job.")
    _check_booking(scheduled_start, scheduled_end)
    snapshot_scope = "\n".join(
        f"{line['quantity']} {line['unit']} · {line['description']}" for line in estimate.accepted_snapshot["lines"]
    )
    if scope and scope != snapshot_scope:
        require_admin(actor)
    job = Job.objects.create(
        estimate=estimate,
        customer=estimate.customer,
        property=estimate.property,
        salesperson=estimate.salesperson,
        scheduled_start=scheduled_start,
        scheduled_end=scheduled_end,
        scope=scope or snapshot_scope,
        checklist=checklist
        or ["Confirm service scope", "Complete quoted cleaning", "Inspect glass and tidy work area"],
        recurring_plan=recurring_plan,
        recurrence_key=recurrence_key,
    )
    Lead.objects.filter(pk=estimate.lead_id).update(status=Lead.Status.WON)
    _audit(actor, "job.scheduled", job, start=scheduled_start.isoformat(), end=scheduled_end.isoformat())
    notify_admins("job.scheduled", "A scheduled job needs an assignment", job)
    return job


@transaction.atomic
def offer_job(*, actor, job, cleaner, fixed_amount, expires_at=None, crew_slot=1, supersedes=None):
    require_admin(actor)
    _schedule_lock()
    job = Job.objects.select_for_update().get(pk=job.pk)
    if not has_role(cleaner, "Cleaner"):
        raise ValidationError("Choose an active cleaner.")
    if job.status not in ["scheduled", "offered", "confirmed"]:
        raise ValidationError("Assignments cannot change after work begins; review or cancel the job first.")
    amount = money(fixed_amount)
    if amount < 0 or not 1 <= crew_slot <= job.required_crew:
        raise ValidationError("Enter valid fixed pay and a required crew slot.")
    expires_at = expires_at or min(timezone.now() + timedelta(days=2), job.scheduled_start)
    if expires_at <= timezone.now() or expires_at > job.scheduled_start:
        raise ValidationError("Offer expiration must be in the future and no later than the appointment.")
    if supersedes:
        supersedes = JobOffer.objects.select_for_update().get(pk=supersedes.pk)
        if (
            supersedes.job_id != job.pk
            or supersedes.crew_slot != crew_slot
            or supersedes.status not in ["accepted", "offered"]
        ):
            raise ValidationError("Only this crew slot's current offer may be superseded.")
        _withdraw_offer(actor, supersedes, JobOffer.Status.SUPERSEDED, "New assignment terms require acceptance")
    live = job.offers.select_for_update().filter(crew_slot=crew_slot, status__in=["offered", "accepted"])
    for old in live:
        if old.status == "offered" and old.expires_at <= timezone.now():
            _withdraw_offer(actor, old, JobOffer.Status.EXPIRED, "Offer expired")
        else:
            raise ValidationError("Withdraw or supersede the current offer before offering this crew slot.")
    offer = JobOffer.objects.create(
        job=job,
        cleaner=cleaner,
        offered_by=actor,
        crew_slot=crew_slot,
        fixed_amount=amount,
        scope_snapshot=job.scope,
        scheduled_start_snapshot=job.scheduled_start,
        scheduled_end_snapshot=job.scheduled_end,
        expires_at=expires_at,
        supersedes=supersedes,
    )
    job.status = Job.Status.OFFERED
    job.save(update_fields=["status", "updated_at"])
    _audit(actor, "offer.created", offer, fixed_amount=str(amount), crew_slot=crew_slot)
    notify(
        recipient=cleaner,
        kind="offer.created",
        title="You have a new job offer",
        body="Review the schedule, service scope, and agreed pay in your workspace.",
        link=f"/crew/offers/{offer.pk}/",
        obj=offer,
        dedupe_key=f"offer.created:{offer.pk}",
    )
    return offer


def _withdraw_offer(actor, offer, status, reason):
    for payout in offer.payouts.filter(status__in=["pending", "payable", "paid"]):
        if payout.status != "pending":
            raise ValidationError("Approved compensation needs an explicit financial reversal before reassignment.")
        payout.status, payout.reason = CleanerPayout.Status.REVERSED, reason
        payout.save(update_fields=["status", "reason", "updated_at"])
    offer.status, offer.responded_at, offer.rejection_reason = status, timezone.now(), reason
    offer.save(update_fields=["status", "responded_at", "rejection_reason", "updated_at"])
    _audit(actor, f"offer.{status}", offer, reason=reason)
    notify(
        recipient=offer.cleaner,
        kind=f"offer.{status}",
        title="Your job offer was updated",
        link=f"/crew/offers/{offer.pk}/",
        obj=offer,
        dedupe_key=f"offer.{status}:{offer.pk}",
    )


@transaction.atomic
def withdraw_offer(*, actor, offer, reason):
    require_admin(actor)
    _schedule_lock()
    offer = JobOffer.objects.select_for_update().get(pk=offer.pk)
    if offer.status not in ["offered", "accepted"] or not reason.strip():
        raise ValidationError("Only an active offer can be withdrawn, with a reason.")
    if offer.job.status not in ["scheduled", "offered", "confirmed"]:
        raise ValidationError("Review the job before withdrawing an assignment after work begins.")
    _withdraw_offer(actor, offer, JobOffer.Status.WITHDRAWN, reason)
    _refresh_assignment_status(offer.job)
    return offer


def _refresh_assignment_status(job):
    accepted = job.offers.filter(status="accepted").count()
    status = (
        "confirmed"
        if accepted >= job.required_crew
        else "offered"
        if job.offers.filter(status="offered").exists()
        else "scheduled"
    )
    Job.objects.filter(pk=job.pk).update(status=status)


@transaction.atomic
def respond_to_offer(*, actor, offer, accept, reason=""):
    if not has_role(actor, "Cleaner") or offer.cleaner_id != actor.pk:
        raise PermissionDenied("Only the offered cleaner can respond.")
    _schedule_lock()
    offer = JobOffer.objects.select_for_update().select_related("job").get(pk=offer.pk)
    job = Job.objects.select_for_update().get(pk=offer.job_id)
    if offer.status != JobOffer.Status.OFFERED or offer.expires_at <= timezone.now():
        raise ValidationError("This offer has expired or is no longer open.")
    if job.status not in ["scheduled", "offered", "confirmed"]:
        raise ValidationError("This job no longer accepts assignment responses.")
    if (
        offer.scope_snapshot != job.scope
        or offer.scheduled_start_snapshot != job.scheduled_start
        or offer.scheduled_end_snapshot != job.scheduled_end
    ):
        raise ValidationError("The job has changed. Ask the administrator for an updated offer.")
    if accept:
        start, end = job.scheduled_start, job.scheduled_end
        if AvailabilityBlock.objects.filter(staff=actor, starts_at__lt=end, ends_at__gt=start).exists():
            raise ValidationError("This assignment overlaps your time off or availability block.")
        if (
            JobOffer.objects.filter(
                cleaner=actor, status="accepted", scheduled_start_snapshot__lt=end, scheduled_end_snapshot__gt=start
            )
            .exclude(job=job)
            .exists()
        ):
            raise ValidationError("This assignment conflicts with an accepted job.")
        offer.status = JobOffer.Status.ACCEPTED
        offer.accepted_terms = {
            "fixed_amount": str(offer.fixed_amount),
            "scope": offer.scope_snapshot,
            "scheduled_start": offer.scheduled_start_snapshot.isoformat(),
            "scheduled_end": offer.scheduled_end_snapshot.isoformat(),
            "cleaner_id": str(actor.pk),
            "crew_slot": offer.crew_slot,
        }
        CleanerPayout.objects.create(offer=offer, cleaner=actor, amount=offer.fixed_amount)
    else:
        offer.status, offer.rejection_reason = JobOffer.Status.REJECTED, reason
    offer.responded_at = timezone.now()
    offer.save(update_fields=["status", "accepted_terms", "rejection_reason", "responded_at", "updated_at"])
    _refresh_assignment_status(job)
    _audit(actor, f"offer.{offer.status}", offer, reason=reason)
    notify_admins(f"offer.{offer.status}", f"A cleaner {offer.status} an assignment", offer)
    notify(
        recipient=actor,
        kind=f"offer.{offer.status}",
        title="Assignment confirmed" if accept else "Offer response recorded",
        link=f"/crew/jobs/{job.pk}/" if accept else f"/crew/offers/{offer.pk}/",
        obj=offer,
        dedupe_key=f"offer.{offer.status}:{offer.pk}",
    )
    return offer


@transaction.atomic
def reschedule_job(*, actor, job, scheduled_start, scheduled_end, reason, scope=None):
    require_admin(actor)
    _schedule_lock()
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.status not in ["scheduled", "offered", "confirmed"] or not reason.strip():
        raise ValidationError("Only upcoming jobs can be rescheduled, with a reason.")
    _validate_window(scheduled_start, scheduled_end)
    if scheduled_start < timezone.now():
        raise ValidationError("Choose a future appointment.")
    if (
        scheduled_start == job.scheduled_start
        and scheduled_end == job.scheduled_end
        and (scope is None or scope == job.scope)
    ):
        raise ValidationError("Choose a different appointment time before saving.")
    _check_booking(scheduled_start, scheduled_end, exclude_job=job)
    previous_window = {"start": job.scheduled_start.isoformat(), "end": job.scheduled_end.isoformat()}
    for offer in job.offers.select_for_update().filter(status__in=["offered", "accepted"]):
        _withdraw_offer(actor, offer, JobOffer.Status.SUPERSEDED, reason)
    job.scheduled_start, job.scheduled_end, job.status = scheduled_start, scheduled_end, Job.Status.SCHEDULED
    if scope is not None:
        job.scope = scope
    job.save(update_fields=["scheduled_start", "scheduled_end", "scope", "status", "updated_at"])
    _audit(
        actor,
        "job.rescheduled",
        job,
        reason=reason,
        previous=previous_window,
        current={"start": scheduled_start.isoformat(), "end": scheduled_end.isoformat()},
    )
    return job


@transaction.atomic
def transition_job(*, actor, job, status, notes="", completed_checklist=None):
    job = Job.objects.select_for_update().get(pk=job.pk)
    if not is_admin(actor) and (
        not has_role(actor, "Cleaner") or not job.offers.filter(cleaner=actor, status="accepted").exists()
    ):
        raise PermissionDenied("Only an assigned cleaner can update this job.")
    allowed = {
        "confirmed": {"en_route", "arrived", "in_progress", "issue"},
        "en_route": {"arrived", "in_progress", "issue"},
        "arrived": {"in_progress", "issue"},
        "in_progress": {"completion_submitted", "issue"},
        "issue": {"in_progress", "completion_submitted"},
    }
    if status not in allowed.get(job.status, set()):
        raise ValidationError("This job status change is not allowed.")
    if completed_checklist is not None:
        if not isinstance(completed_checklist, list) or any(item not in job.checklist for item in completed_checklist):
            raise ValidationError("Choose valid checklist items for this job.")
        job.completed_checklist = completed_checklist
    if status == "completion_submitted":
        if set(job.completed_checklist) != set(job.checklist):
            raise ValidationError("Complete the job checklist or report an issue before submitting.")
        if job.requires_photos and (not hasattr(job, "evidence") or not job.evidence.exists()):
            raise ValidationError("This job requires a private evidence photo before submission.")
        job.submitted_at = timezone.now()
    if status == "issue" and not notes.strip():
        raise ValidationError("Describe the issue so the administrator can help.")
    job.status = status
    if notes:
        job.completion_notes = (job.completion_notes + "\n" + notes).strip()
    job.save(update_fields=["status", "completed_checklist", "completion_notes", "submitted_at", "updated_at"])
    _audit(actor, f"job.{status}", job)
    if status in ["completion_submitted", "issue"]:
        notify_admins(
            f"job.{status}",
            "A job needs completion review" if status == "completion_submitted" else "A cleaner reported an issue",
            job,
            suffix=str(job.updated_at.timestamp()),
        )
    return job


@transaction.atomic
def approve_completion(*, actor, job, approved=True, reason=""):
    require_admin(actor)
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.status != Job.Status.COMPLETION_SUBMITTED:
        raise ValidationError("This job is not awaiting completion review.")
    if not approved:
        if not reason.strip():
            raise ValidationError("Explain what needs correction.")
        job.status = Job.Status.IN_PROGRESS
        job.completion_notes = (job.completion_notes + "\nCorrection requested: " + reason).strip()
        job.save(update_fields=["status", "completion_notes", "updated_at"])
        _audit(actor, "job.completion_returned", job, reason=reason)
        for offer in job.offers.filter(status="accepted"):
            notify(
                recipient=offer.cleaner,
                kind="job.completion_returned",
                title="A job needs a correction",
                link=f"/crew/jobs/{job.pk}/",
                obj=job,
            )
        return job
    job.status, job.approved_at, job.approved_by = Job.Status.COMPLETED, timezone.now(), actor
    job.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
    for offer in job.offers.select_for_update().filter(status="accepted"):
        payout = offer.payouts.select_for_update().get(status=CleanerPayout.Status.PENDING)
        payout.status, payout.approved_at, payout.approved_by = CleanerPayout.Status.PAYABLE, timezone.now(), actor
        payout.save(update_fields=["status", "approved_at", "approved_by", "updated_at"])
        offer.status = JobOffer.Status.COMPLETED
        offer.save(update_fields=["status", "updated_at"])
        _audit(actor, "payout.payable", payout, amount=str(payout.amount))
        notify(
            recipient=offer.cleaner,
            kind="payout.payable",
            title="Your completed job was approved",
            body="Your agreed job pay is now payable.",
            link="/crew/compensation/",
            obj=payout,
            dedupe_key=f"payout.payable:{payout.pk}",
        )
    _audit(actor, "job.completion_approved", job)
    return job


@transaction.atomic
def cancel_job(*, actor, job, reason):
    require_admin(actor)
    _schedule_lock()
    job = Job.objects.select_for_update().get(pk=job.pk)
    if job.status in ["completed", "canceled"] or not reason.strip():
        raise ValidationError("Only an uncompleted job can be canceled, with a reason.")
    for offer in job.offers.select_for_update().filter(status__in=["offered", "accepted"]):
        _withdraw_offer(actor, offer, JobOffer.Status.WITHDRAWN, reason)
    job.status, job.cancellation_reason = Job.Status.CANCELED, reason
    job.save(update_fields=["status", "cancellation_reason", "updated_at"])
    _audit(actor, "job.canceled", job, reason=reason)
    return job


@transaction.atomic
def create_invoice(*, actor, job, due_date=None, purchase_order=""):
    require_admin(actor)
    job = Job.objects.select_for_update().select_related("estimate", "customer", "property").get(pk=job.pk)
    if job.status != Job.Status.COMPLETED:
        raise ValidationError("Approve completion before creating the invoice.")
    existing = job.invoices.exclude(status="void").first()
    if existing:
        return existing
    snap = job.estimate.accepted_snapshot
    if not snap:
        raise ValidationError("The accepted estimate snapshot is missing.")
    invoice = Invoice.objects.create(
        job=job,
        customer=job.customer,
        subtotal=money(snap["subtotal"]),
        discount=money(snap["discount"]),
        tax=money(snap["tax"]),
        total=money(snap["total"]),
        due_date=due_date or timezone.localdate() + timedelta(days=job.customer.payment_terms_days),
        terms=snap["terms"],
        purchase_order=purchase_order,
        billing_snapshot={"name": job.customer.name, "email": job.customer.email, "address": job.property.address},
    )
    for position, line in enumerate(snap["lines"]):
        InvoiceLine.objects.create(
            invoice=invoice,
            description=line["description"],
            quantity=money(line["quantity"]),
            unit=line["unit"],
            unit_price=money(line["unit_price"]),
            total=money(line["total"]),
            position=position,
        )
    _audit(actor, "invoice.created", invoice)
    return invoice


@transaction.atomic
def issue_invoice(*, actor, job=None, invoice=None, due_date=None, purchase_order=""):
    require_admin(actor)
    _schedule_lock()
    if invoice is None:
        if job is None:
            raise ValidationError("Choose a completed job to invoice.")
        invoice = create_invoice(actor=actor, job=job, due_date=due_date, purchase_order=purchase_order)
    invoice = Invoice.objects.select_for_update().select_related("job__estimate", "customer").get(pk=invoice.pk)
    if invoice.status != Invoice.Status.DRAFT:
        if invoice.status != Invoice.Status.VOID:
            return invoice
        raise ValidationError("A void invoice cannot be issued again.")
    year = timezone.localdate().year
    InvoiceSequence.objects.get_or_create(year=year)
    sequence = InvoiceSequence.objects.select_for_update().get(year=year)
    invoice.number = f"FGK-{year}-{sequence.next_number:05d}"
    sequence.next_number += 1
    sequence.save(update_fields=["next_number"])
    invoice.status, invoice.issued_at = Invoice.Status.ISSUED, timezone.now()
    invoice.issued_snapshot = {
        "number": invoice.number,
        "billing": invoice.billing_snapshot,
        "subtotal": str(invoice.subtotal),
        "discount": str(invoice.discount),
        "tax": str(invoice.tax),
        "total": str(invoice.total),
        "terms": invoice.terms,
        "due_date": invoice.due_date.isoformat(),
        "purchase_order": invoice.purchase_order,
        "lines": [
            {
                "description": line.description,
                "quantity": str(line.quantity),
                "unit": line.unit,
                "unit_price": str(line.unit_price),
                "total": str(line.total),
            }
            for line in invoice.lines.all()
        ],
    }
    invoice.save(update_fields=["number", "status", "issued_at", "issued_snapshot", "updated_at"])
    _create_pending_commission(invoice)
    if invoice.total == 0:
        _update_invoice_payment_state(invoice)
    token = create_access_token(actor=actor, obj=invoice, lifetime_days=90)
    site_url = getattr(settings, "SITE_URL", "http://127.0.0.1:8000").rstrip("/")
    _queue_message(
        key=f"invoice:{invoice.pk}:issued",
        customer=invoice.customer,
        subject=f"FirstGlanceKnox invoice {invoice.number}",
        body=f"Your invoice is ready:\n{site_url}/portal/invoice/{token}/\n\nTotal: ${invoice.total}\nDue: {invoice.due_date}\nPlease contact FirstGlanceKnox to arrange payment. Online payment processing is not enabled.",
    )
    _audit(actor, "invoice.issued", invoice, number=invoice.number, total=str(invoice.total))
    return invoice


@transaction.atomic
def send_invoice(*, actor, invoice):
    require_admin(actor)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status in ["draft", "void"]:
        raise ValidationError("Only an issued, non-void invoice can be sent.")
    # An outstanding queue record is reused; deliberate resend after delivery gets a new entry.
    pending = OutboundMessage.objects.filter(
        dedupe_key__startswith=f"invoice:{invoice.pk}:", sent_at__isnull=True
    ).first()
    if pending:
        return pending
    token = create_access_token(actor=actor, obj=invoice)
    message = _queue_message(
        key=f"invoice:{invoice.pk}:resend:{secrets.token_hex(8)}",
        customer=invoice.customer,
        subject=f"FirstGlanceKnox invoice {invoice.number}",
        body=f"Your invoice is ready to view and download:\n{settings.SITE_URL}/portal/invoice/{token}/\n\nBalance: ${invoice.balance}\n{settings.PAYMENT_INSTRUCTIONS}",
    )
    _audit(actor, "invoice.delivery_queued", invoice)
    return message


def _create_pending_commission(invoice):
    estimate = invoice.job.estimate
    snap = estimate.accepted_snapshot
    if not estimate.salesperson_id or Decimal(snap.get("commission_rate", "0")) <= 0:
        return None
    entry = invoice.commissions.filter(status__in=["pending", "earned", "paid"]).first()
    if entry:
        return entry
    return CommissionEntry.objects.create(
        salesperson_id=estimate.salesperson_id,
        estimate=estimate,
        invoice=invoice,
        rate_snapshot=money(snap["commission_rate"]),
        base_amount=money(snap["commissionable_base"]),
        amount=money(Decimal(snap["commissionable_base"]) * Decimal(snap["commission_rate"]) / 100),
    )


def _update_invoice_payment_state(invoice):
    invoice.status = (
        Invoice.Status.PAID
        if invoice.balance == 0
        else Invoice.Status.PARTIAL
        if invoice.paid_amount > 0
        else Invoice.Status.ISSUED
    )
    invoice.save(update_fields=["paid_amount", "status", "updated_at"])
    if invoice.status == Invoice.Status.PAID:
        entry = _create_pending_commission(invoice)
        if entry and entry.status == CommissionEntry.Status.PENDING:
            entry.status, entry.earned_at = CommissionEntry.Status.EARNED, timezone.now()
            entry.save(update_fields=["status", "earned_at", "updated_at"])
            _audit(None, "commission.earned", entry, amount=str(entry.amount))
            notify(
                recipient=entry.salesperson,
                kind="commission.earned",
                title="A commission is now earned",
                body="The related invoice has been paid in full.",
                link="/crew/compensation/",
                obj=entry,
                dedupe_key=f"commission.earned:{entry.pk}",
            )


@transaction.atomic
def record_payment(*, actor, invoice, amount, method="cash", reference="", note="", idempotency_key=None):
    require_admin(actor)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    amount = money(amount)
    if idempotency_key:
        existing = Payment.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.invoice_id != invoice.pk or existing.amount != amount:
                raise ValidationError("That payment reference was already used for different payment details.")
            return existing
    if invoice.status not in [Invoice.Status.ISSUED, Invoice.Status.PARTIAL]:
        raise ValidationError("Payments can only be recorded on an open issued invoice.")
    if amount <= 0 or amount > invoice.balance:
        raise ValidationError("Payment must be greater than zero and cannot exceed the balance.")
    if method not in ["cash", "check", "bank_transfer", "other", "card_external"]:
        raise ValidationError("Choose a supported manual payment method.")
    payment = Payment.objects.create(
        invoice=invoice,
        amount=amount,
        method=method,
        reference=reference,
        note=note,
        recorded_by=actor,
        idempotency_key=idempotency_key,
    )
    invoice.paid_amount = money(invoice.paid_amount + amount)
    _update_invoice_payment_state(invoice)
    _audit(actor, "payment.recorded", payment, amount=str(amount), invoice_id=str(invoice.pk))
    notify_admins("payment.recorded", "A customer payment was recorded", payment)
    _queue_message(
        key=f"payment:{payment.pk}:receipt",
        customer=invoice.customer,
        subject=f"Payment recorded for {invoice.number}",
        body=f"We recorded your payment of ${amount}.\nRemaining invoice balance: ${invoice.balance}.\n\nThank you,\nFirstGlanceKnox",
    )
    return payment


def _reverse_commission(actor, entry, reason):
    original_status = entry.status
    entry.status, entry.reason = CommissionEntry.Status.REVERSED, reason
    entry.save(update_fields=["status", "reason", "updated_at"])
    reverse = CommissionEntry.objects.create(
        salesperson=entry.salesperson,
        estimate=entry.estimate,
        invoice=entry.invoice,
        rate_snapshot=entry.rate_snapshot,
        base_amount=-entry.base_amount,
        amount=-entry.amount,
        status=CommissionEntry.Status.REVERSED,
        reason=reason,
        reversal_of=entry,
    )
    _audit(actor, "commission.reversed", reverse, previous_status=original_status, amount=str(reverse.amount))
    notify(
        recipient=entry.salesperson,
        kind="commission.reversed",
        title="A commission adjustment needs review",
        link="/crew/compensation/",
        obj=reverse,
        dedupe_key=f"commission.reversed:{entry.pk}",
    )
    return reverse


@transaction.atomic
def reverse_payment(*, actor, payment, reason):
    require_admin(actor)
    invoice = Invoice.objects.select_for_update().get(pk=payment.invoice_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.reversal_of_id or Payment.objects.filter(reversal_of=payment).exists():
        raise ValidationError("This payment is a reversal or has already been reversed.")
    if not reason.strip():
        raise ValidationError("Explain the payment reversal.")
    reversal = Payment.objects.create(
        invoice=invoice,
        amount=-payment.amount,
        method=payment.method,
        reference=payment.reference,
        note=reason,
        recorded_by=actor,
        reversal_of=payment,
    )
    invoice.paid_amount = money(invoice.paid_amount - payment.amount)
    for entry in invoice.commissions.select_for_update().filter(status__in=["earned", "paid"]):
        _reverse_commission(actor, entry, reason)
    _update_invoice_payment_state(invoice)
    _audit(actor, "payment.reversed", reversal, amount=str(reversal.amount), reason=reason)
    notify_admins("payment.reversed", "A payment reversal needs review", reversal)
    return reversal


@transaction.atomic
def void_invoice(*, actor, invoice, reason):
    require_admin(actor)
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status == "void" or invoice.paid_amount != 0 or not reason.strip():
        raise ValidationError("Reverse recorded payments before voiding an invoice, and provide a reason.")
    for entry in invoice.commissions.select_for_update().filter(status__in=["pending", "earned", "paid"]):
        _reverse_commission(actor, entry, reason)
    invoice.status, invoice.void_reason = Invoice.Status.VOID, reason
    invoice.save(update_fields=["status", "void_reason", "updated_at"])
    _audit(actor, "invoice.voided", invoice, reason=reason)
    return invoice


@transaction.atomic
def mark_commission_paid(*, actor, entry, reference):
    require_admin(actor)
    entry = CommissionEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.status != CommissionEntry.Status.EARNED or not reference.strip():
        raise ValidationError("Only earned commission may be marked paid, with a payment reference.")
    entry.status, entry.paid_at, entry.payment_reference = CommissionEntry.Status.PAID, timezone.now(), reference
    entry.save(update_fields=["status", "paid_at", "payment_reference", "updated_at"])
    _audit(actor, "commission.paid", entry, reference=reference, amount=str(entry.amount))
    notify(
        recipient=entry.salesperson,
        kind="commission.paid",
        title="Your commission was marked paid",
        link="/crew/compensation/",
        obj=entry,
        dedupe_key=f"commission.paid:{entry.pk}",
    )
    return entry


@transaction.atomic
def mark_payout_paid(*, actor, payout, reference):
    require_admin(actor)
    payout = CleanerPayout.objects.select_for_update().get(pk=payout.pk)
    if payout.status != CleanerPayout.Status.PAYABLE or not reference.strip():
        raise ValidationError("Only approved payable compensation may be marked paid, with a reference.")
    payout.status, payout.paid_at, payout.payment_reference = CleanerPayout.Status.PAID, timezone.now(), reference
    payout.save(update_fields=["status", "paid_at", "payment_reference", "updated_at"])
    _audit(actor, "payout.paid", payout, reference=reference, amount=str(payout.amount))
    notify(
        recipient=payout.cleaner,
        kind="payout.paid",
        title="Your job pay was marked paid",
        link="/crew/compensation/",
        obj=payout,
        dedupe_key=f"payout.paid:{payout.pk}",
    )
    return payout


@transaction.atomic
def reverse_payout(*, actor, payout, reason):
    require_admin(actor)
    payout = CleanerPayout.objects.select_for_update().get(pk=payout.pk)
    if payout.status == CleanerPayout.Status.REVERSED or payout.reversal_of_id or not reason.strip():
        raise ValidationError("Choose an unreversed payout and provide a reason.")
    previous_status = payout.status
    payout.status, payout.reason = CleanerPayout.Status.REVERSED, reason
    payout.save(update_fields=["status", "reason", "updated_at"])
    reversal = CleanerPayout.objects.create(
        offer=payout.offer,
        cleaner=payout.cleaner,
        amount=-payout.amount,
        status=CleanerPayout.Status.REVERSED,
        reason=reason,
        reversal_of=payout,
    )
    _audit(
        actor, "payout.reversed", reversal, amount=str(reversal.amount), previous_status=previous_status, reason=reason
    )
    return reversal


@transaction.atomic
def generate_recurring_visit(*, actor, plan, expected_visit=None):
    require_admin(actor)
    _schedule_lock()
    plan = RecurringPlan.objects.select_for_update().get(pk=plan.pk)
    if expected_visit is not None and expected_visit != plan.next_visit_at:
        raise ValidationError(
            "This plan has changed or the visit was already generated. Refresh the schedule before generating another visit."
        )
    if not plan.active or plan.interval_days < 1 or plan.duration_minutes < 1:
        raise ValidationError("This recurring plan is not active or needs a valid interval.")
    if (
        plan.property.customer_id != plan.customer_id
        or plan.estimate.customer_id != plan.customer_id
        or plan.estimate.property_id != plan.property_id
    ):
        raise ValidationError("Recurring plan customer, property, and estimate must agree.")
    key = f"{plan.pk}:{plan.next_visit_at.isoformat()}"
    existing = Job.objects.filter(recurrence_key=key).first()
    if existing:
        return existing
    job = schedule_job(
        actor=actor,
        estimate=plan.estimate,
        scheduled_start=plan.next_visit_at,
        scheduled_end=plan.next_visit_at + timedelta(minutes=plan.duration_minutes),
        recurring_plan=plan,
        recurrence_key=key,
    )
    plan.next_visit_at += timedelta(days=plan.interval_days)
    plan.save(update_fields=["next_visit_at", "updated_at"])
    _audit(actor, "recurring.visit_generated", job, plan_id=str(plan.pk))
    return job
