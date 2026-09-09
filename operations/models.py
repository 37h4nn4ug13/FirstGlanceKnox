import uuid
from builtins import property as computed_property

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Record(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class Customer(Record):
    class Kind(models.TextChoices):
        RESIDENTIAL = "residential", "Residential"
        COMMERCIAL = "commercial", "Commercial"

    name = models.CharField(max_length=180)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.RESIDENTIAL)
    email = models.EmailField(blank=True, db_index=True)
    phone = models.CharField(max_length=40, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="customer_accounts"
    )
    active = models.BooleanField(default=True)
    do_not_contact = models.BooleanField(default=False)
    marketing_consent = models.BooleanField(default=False)
    payment_terms_days = models.PositiveSmallIntegerField(default=14)
    internal_notes = models.TextField(blank=True)
    tags = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class Contact(Record):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=180)
    title = models.CharField(max_length=120, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    preferred_channel = models.CharField(max_length=20, default="email")
    is_primary = models.BooleanField(default=False)
    is_billing = models.BooleanField(default=False)
    is_site = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} · {self.customer}"


class Property(Record):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="properties")
    name = models.CharField(max_length=140, blank=True)
    address_line1 = models.CharField(max_length=240)
    address_line2 = models.CharField(max_length=180, blank=True)
    city = models.CharField(max_length=100, default="Knoxville")
    state = models.CharField(max_length=40, default="TN")
    postal_code = models.CharField(max_length=20, blank=True)
    kind = models.CharField(max_length=20, choices=Customer.Kind.choices, default=Customer.Kind.RESIDENTIAL)
    address_key = models.CharField(max_length=320, db_index=True, blank=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    stories = models.PositiveSmallIntegerField(default=1)
    approximate_windows = models.PositiveIntegerField(null=True, blank=True)
    access_instructions = models.TextField(blank=True)
    hazards = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)

    @computed_property
    def address(self):
        return ", ".join(
            filter(None, [self.address_line1, self.address_line2, self.city, self.state, self.postal_code])
        )

    def __str__(self):
        return self.name or self.address_line1


class Lead(Record):
    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        FOLLOW_UP = "follow_up", "Follow-up due"
        ESTIMATE_SENT = "estimate_sent", "Estimate sent"
        WON = "won", "Won / scheduled"
        LOST = "lost", "Lost"
        DO_NOT_CONTACT = "do_not_contact", "Do not contact"

    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="leads")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="leads")
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_leads"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_leads"
    )
    status = models.CharField(max_length=24, choices=Status.choices, default=Status.NEW, db_index=True)
    source = models.CharField(max_length=40, default="website", db_index=True)
    services = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)
    preferred_date = models.DateField(null=True, blank=True)
    follow_up_at = models.DateTimeField(null=True, blank=True, db_index=True)
    idempotency_key = models.CharField(max_length=100, null=True, blank=True, unique=True)

    def __str__(self):
        return f"{self.customer} · {self.get_status_display()}"


class LeadVisit(Record):
    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="visits")
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    outcome = models.CharField(max_length=40)
    notes = models.TextField(blank=True)
    visited_at = models.DateTimeField(default=timezone.now)


class PriceBookItem(Record):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    unit = models.CharField(max_length=40, default="window")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(0)])
    category = models.CharField(max_length=20, choices=Customer.Kind.choices, blank=True)
    active = models.BooleanField(default=True)
    requires_approval = models.BooleanField(default=False)
    commissionable = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.CheckConstraint(condition=Q(unit_price__gte=0), name="pricebook_nonnegative")]

    def __str__(self):
        return f"{self.name} (${self.unit_price}/{self.unit})"


class Estimate(Record):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Needs admin approval"
        SENT = "sent", "Sent"
        VIEWED = "viewed", "Viewed"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"
        EXPIRED = "expired", "Expired"
        SUPERSEDED = "superseded", "Superseded"

    lead = models.ForeignKey(Lead, on_delete=models.PROTECT, related_name="estimates")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="estimates")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="estimates")
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="estimates"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    commission_rate_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    commissionable_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    customer_notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    terms = models.TextField(
        default="Scope and pricing are valid until the expiration date. Scheduling is subject to availability."
    )
    expires_on = models.DateField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.CharField(max_length=180, blank=True)
    accepted_snapshot = models.JSONField(default=dict, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_estimates"
    )
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="revisions")
    public_token_version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(total__gte=0) & Q(discount__gte=0), name="estimate_amounts_nonnegative")
        ]

    @computed_property
    def number(self):
        return f"EST-{str(self.id)[:8].upper()}"

    def __str__(self):
        return self.number


class EstimateLine(Record):
    estimate = models.ForeignKey(Estimate, on_delete=models.CASCADE, related_name="lines")
    price_book_item = models.ForeignKey(PriceBookItem, null=True, blank=True, on_delete=models.SET_NULL)
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    unit = models.CharField(max_length=40, default="service")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    commissionable = models.BooleanField(default=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0) & Q(unit_price__gte=0) & Q(total__gte=0), name="estimate_line_valid_amounts"
            )
        ]


class ScheduleLock(models.Model):
    """Singleton row serializes all booking writes, including empty-calendar races."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)


class AvailabilityBlock(Record):
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(ends_at__gt=models.F("starts_at")), name="availability_positive_window")
        ]


class RecurringPlan(Record):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="recurring_plans")
    property = models.ForeignKey(Property, on_delete=models.PROTECT)
    estimate = models.ForeignKey(Estimate, on_delete=models.PROTECT)
    name = models.CharField(max_length=180)
    interval_days = models.PositiveIntegerField(default=90, validators=[MinValueValidator(1)])
    duration_minutes = models.PositiveIntegerField(default=120, validators=[MinValueValidator(1)])
    next_visit_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    purchase_order = models.CharField(max_length=100, blank=True)


class Job(Record):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled / unassigned"
        OFFERED = "offered", "Assignment pending"
        CONFIRMED = "confirmed", "Confirmed"
        EN_ROUTE = "en_route", "En route"
        ARRIVED = "arrived", "Arrived"
        IN_PROGRESS = "in_progress", "In progress"
        ISSUE = "issue", "Issue reported"
        COMPLETION_SUBMITTED = "completion_submitted", "Completion review"
        COMPLETED = "completed", "Completed / approved"
        CANCELED = "canceled", "Canceled"

    estimate = models.ForeignKey(Estimate, on_delete=models.PROTECT, related_name="jobs")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="jobs")
    property = models.ForeignKey(Property, on_delete=models.PROTECT, related_name="jobs")
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="sold_jobs"
    )
    scheduled_start = models.DateTimeField(db_index=True)
    scheduled_end = models.DateTimeField()
    scope = models.TextField()
    status = models.CharField(max_length=28, choices=Status.choices, default=Status.SCHEDULED, db_index=True)
    required_crew = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    customer_notes = models.TextField(blank=True)
    crew_instructions = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    checklist = models.JSONField(default=list, blank=True)
    completed_checklist = models.JSONField(default=list, blank=True)
    requires_photos = models.BooleanField(default=False)
    completion_notes = models.TextField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_jobs"
    )
    cancellation_reason = models.TextField(blank=True)
    recurring_plan = models.ForeignKey(
        RecurringPlan, null=True, blank=True, on_delete=models.PROTECT, related_name="jobs"
    )
    recurrence_key = models.CharField(max_length=160, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["scheduled_start"]
        constraints = [
            models.CheckConstraint(
                condition=Q(scheduled_end__gt=models.F("scheduled_start")), name="job_positive_window"
            )
        ]

    @computed_property
    def number(self):
        return f"JOB-{str(self.id)[:8].upper()}"

    @computed_property
    def duration_minutes(self):
        return int((self.scheduled_end - self.scheduled_start).total_seconds() // 60)

    def __str__(self):
        return self.number


class JobOffer(Record):
    class Status(models.TextChoices):
        OFFERED = "offered", "Offered"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        EXPIRED = "expired", "Expired"
        WITHDRAWN = "withdrawn", "Withdrawn"
        SUPERSEDED = "superseded", "Superseded"
        COMPLETED = "completed", "Completed"

    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="offers")
    cleaner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="job_offers")
    offered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="made_offers"
    )
    crew_slot = models.PositiveSmallIntegerField(default=1)
    fixed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    scope_snapshot = models.TextField()
    scheduled_start_snapshot = models.DateTimeField()
    scheduled_end_snapshot = models.DateTimeField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFERED)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    accepted_terms = models.JSONField(default=dict, blank=True)
    supersedes = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="revisions")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(fixed_amount__gte=0), name="offer_pay_nonnegative"),
            models.UniqueConstraint(
                fields=["job", "crew_slot"],
                condition=Q(status__in=["offered", "accepted"]),
                name="one_live_offer_per_crew_slot",
            ),
            models.UniqueConstraint(
                fields=["job", "cleaner"],
                condition=Q(status__in=["offered", "accepted"]),
                name="one_live_offer_per_cleaner_job",
            ),
        ]

    def __str__(self):
        return f"{self.job} · {self.cleaner} · {self.get_status_display()}"


class InvoiceSequence(models.Model):
    year = models.PositiveIntegerField(primary_key=True)
    next_number = models.PositiveIntegerField(default=1)


class Invoice(Record):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"
        VOID = "void", "Void"

    job = models.ForeignKey(Job, on_delete=models.PROTECT, related_name="invoices")
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField(max_length=40, unique=True, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    issued_at = models.DateTimeField(null=True, blank=True)
    due_date = models.DateField()
    terms = models.TextField(blank=True)
    purchase_order = models.CharField(max_length=100, blank=True)
    billing_snapshot = models.JSONField(default=dict, blank=True)
    issued_snapshot = models.JSONField(default=dict, blank=True)
    void_reason = models.TextField(blank=True)
    public_token_version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(total__gte=0) & Q(paid_amount__gte=0) & Q(paid_amount__lte=models.F("total")),
                name="invoice_balance_valid",
            ),
            models.UniqueConstraint(fields=["job"], condition=~Q(status="void"), name="one_live_invoice_per_job"),
        ]

    @computed_property
    def balance(self):
        return self.total - self.paid_amount

    @computed_property
    def is_overdue(self):
        return self.status in [self.Status.ISSUED, self.Status.PARTIAL] and self.due_date < timezone.localdate()

    def __str__(self):
        return self.number or f"Draft {str(self.id)[:8]}"


class InvoiceLine(Record):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")
    description = models.CharField(max_length=240)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=40)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]


class Payment(Record):
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=40, default="cash")
    reference = models.CharField(max_length=160, blank=True)
    note = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    received_at = models.DateTimeField(default=timezone.now)
    reversal_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")
    idempotency_key = models.CharField(max_length=100, unique=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(Q(reversal_of__isnull=True) & Q(amount__gt=0))
                | (Q(reversal_of__isnull=False) & Q(amount__lt=0)),
                name="payment_signed_by_kind",
            )
        ]


class CommissionEntry(Record):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        EARNED = "earned", "Earned"
        PAID = "paid", "Paid"
        REVERSED = "reversed", "Reversed"

    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commissions")
    estimate = models.ForeignKey(Estimate, on_delete=models.PROTECT, related_name="commissions")
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="commissions")
    rate_snapshot = models.DecimalField(max_digits=5, decimal_places=2)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    earned_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    reason = models.TextField(blank=True)
    reversal_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["invoice"],
                condition=Q(status__in=["pending", "earned", "paid"]),
                name="one_active_commission_per_invoice",
            )
        ]


class CleanerPayout(Record):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAYABLE = "payable", "Payable"
        PAID = "paid", "Paid"
        REVERSED = "reversed", "Reversed"

    offer = models.ForeignKey(JobOffer, on_delete=models.PROTECT, related_name="payouts")
    cleaner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="cleaner_payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_payouts"
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_reference = models.CharField(max_length=160, blank=True)
    reason = models.TextField(blank=True)
    reversal_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["offer"],
                condition=Q(status__in=["pending", "payable", "paid"]),
                name="one_active_payout_per_offer",
            )
        ]


class Notification(Record):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=60)
    title = models.CharField(max_length=180)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=300, blank=True)
    object_id = models.UUIDField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=180, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["recipient", "dedupe_key"], name="notification_recipient_dedupe")
        ]


class AuditEvent(Record):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100, db_index=True)
    object_type = models.CharField(max_length=60)
    object_id = models.UUIDField()
    details = models.JSONField(default=dict)


class AccessToken(Record):
    secret_hash = models.CharField(max_length=64, unique=True)
    purpose = models.CharField(max_length=30)
    object_id = models.UUIDField()
    version = models.PositiveIntegerField(default=1)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)


class OutboundMessage(Record):
    """Transactional outbox: no customer information appears in public queue logs."""

    dedupe_key = models.CharField(max_length=180, unique=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=240)
    body = models.TextField()
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.CharField(max_length=240, blank=True)


# Descriptive aliases for integrations that use the longer business terminology.
CleanerPayoutEntry = CleanerPayout
JobAssignment = JobOffer
