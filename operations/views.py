import uuid
from decimal import Decimal
from functools import wraps

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.permissions import staff_required
from . import forms, services
from .models import (
    AuditEvent,
    AvailabilityBlock,
    CleanerPayout,
    CommissionEntry,
    Customer,
    Invoice,
    Job,
    JobOffer,
    Lead,
    LeadVisit,
    Notification,
    Payment,
    PriceBookItem,
    RecurringPlan,
)


def admin_required(view):
    @staff_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        services.require_admin(request.user)
        return view(request, *args, **kwargs)

    return wrapped


def selling_required(user):
    if not (services.is_admin(user) or user.has_role("Salesperson")):
        raise PermissionDenied


def context(request, title, active="dashboard", **kwargs):
    return {
        "page_title": title,
        "active": active,
        "is_admin": services.is_admin(request.user),
        "can_sell": services.is_admin(request.user) or request.user.has_role("Salesperson"),
        "is_cleaner": request.user.has_role("Cleaner"),
        "unread_count": Notification.objects.filter(recipient=request.user, read_at__isnull=True).count(),
        **kwargs,
    }


def page(request, template, title, active="dashboard", **kwargs):
    return render(request, "operations/" + template, context(request, title, active, **kwargs))


def errors(form, error):
    form.add_error(None, "; ".join(error.messages) if isinstance(error, ValidationError) else str(error))


def audit(actor, action, obj, details=None):
    AuditEvent.objects.create(
        actor=actor, action=action, object_type=obj.__class__.__name__, object_id=obj.pk, details=details or {}
    )


@staff_required
def dashboard(request):
    jobs = services.jobs_for(request.user).select_related("customer", "property")
    leads = services.leads_for(request.user).select_related("customer", "property")
    estimates = services.estimates_for(request.user)
    today = timezone.localdate()
    offers = JobOffer.objects.filter(cleaner=request.user, status="offered").select_related(
        "job__customer", "job__property"
    )
    if services.is_admin(request.user):
        metrics = [
            ("New leads", leads.filter(status="new").count(), "Ready for a first conversation", "◎"),
            (
                "Upcoming jobs",
                jobs.filter(scheduled_start__date__gte=today).exclude(status__in=["canceled", "completed"]).count(),
                "On the schedule",
                "▦",
            ),
            ("Awaiting approval", jobs.filter(status="completion_submitted").count(), "Completed work to review", "◇"),
            (
                "Outstanding",
                "$"
                + str(
                    sum(
                        (i.balance for i in Invoice.objects.exclude(status__in=["void", "paid", "draft"])),
                        Decimal("0.00"),
                    )
                ),
                "Customer invoice balances",
                "↗",
            ),
        ]
    elif request.user.has_role("Salesperson"):
        metrics = [
            ("My leads", leads.count(), "Your assigned pipeline", "◎"),
            (
                "Active estimates",
                estimates.filter(status__in=["draft", "sent", "viewed"]).count(),
                "Conversations in progress",
                "▤",
            ),
            ("Booked jobs", jobs.count(), "Your accepted sales", "▦"),
            (
                "Earned commission",
                "$"
                + str(
                    CommissionEntry.objects.filter(salesperson=request.user, status="earned").aggregate(
                        v=Sum("amount")
                    )["v"]
                    or "0.00"
                ),
                "Ready for payout",
                "↗",
            ),
        ]
    else:
        metrics = [
            ("New offers", offers.count(), "Review scope and agreed pay", "◇"),
            ("Today’s jobs", jobs.filter(scheduled_start__date=today).count(), "Your work today", "▦"),
            (
                "Upcoming jobs",
                jobs.filter(scheduled_start__date__gte=today).exclude(status__in=["canceled", "completed"]).count(),
                "Your assigned work",
                "◷",
            ),
            (
                "Payable",
                "$"
                + str(
                    CleanerPayout.objects.filter(cleaner=request.user, status="payable").aggregate(v=Sum("amount"))["v"]
                    or "0.00"
                ),
                "Approved completed work",
                "↗",
            ),
        ]
    return page(
        request,
        "dashboard.html",
        "Overview",
        metrics=metrics,
        jobs=jobs.filter(scheduled_start__date__gte=today).exclude(status__in=["canceled", "completed"])[:5],
        recent_leads=leads[:4],
        offers=offers,
        recent_notifications=Notification.objects.filter(recipient=request.user)[:4],
        review_jobs=jobs.filter(status="completion_submitted")[:4],
        today=today,
    )


@staff_required
def lead_list(request):
    selling_required(request.user)
    records = services.leads_for(request.user).select_related("customer", "property", "assigned_to")
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    if query:
        records = records.filter(
            Q(customer__name__icontains=query)
            | Q(property__address_line1__icontains=query)
            | Q(customer__email__icontains=query)
        )
    if status:
        records = records.filter(status=status)
    return page(
        request,
        "leads.html",
        "Lead pipeline",
        "leads",
        leads=records[:100],
        query=query,
        selected_status=status,
        statuses=Lead.Status.choices,
    )


@staff_required
def quick_lead(request):
    selling_required(request.user)
    form = forms.QuickLeadForm(request.POST or None)
    matches = []
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data.copy()
        confirmed = data.pop("confirm_duplicate")
        # Only expose matches the salesperson already has permission to see.
        matches = (
            services.leads_for(request.user)
            .filter(property__address_line1__iexact=data["address"])
            .select_related("customer", "property")[:5]
        )
        if matches and not confirmed:
            form.add_error(
                None, "A matching address has previous activity. Review it below before recording another visit."
            )
        else:
            try:
                data["name"] = data["name"] or "Prospect at " + data["address"]
                lead = services.capture_lead(actor=request.user, source="door_to_door", **data)
                messages.success(request, "Visit recorded. Your lead is saved.")
                return redirect("operations:lead_detail", pk=lead.pk)
            except ValidationError as error:
                errors(form, error)
    return page(
        request,
        "form.html",
        "Quick lead",
        "leads",
        form=form,
        form_description="A new doorstep conversation. Capture the essentials and keep moving.",
        submit_label="Save lead & visit",
        matches=matches,
        offline_kind="lead",
    )


@staff_required
def lead_detail(request, pk):
    selling_required(request.user)
    lead = get_object_or_404(
        services.leads_for(request.user).select_related("customer", "property", "assigned_to"), pk=pk
    )
    form = forms.LeadUpdateForm(request.POST or None, instance=lead, admin=services.is_admin(request.user))
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            locked = Lead.objects.select_for_update().get(pk=lead.pk)
            old_status = locked.status
            for name, value in form.cleaned_data.items():
                setattr(locked, name, value)
            if (
                old_status == "do_not_contact"
                and locked.status != "do_not_contact"
                and not services.is_admin(request.user)
            ):
                raise PermissionDenied("Only an admin can reopen a do-not-contact lead.")
            locked.save()
            if locked.status == "do_not_contact":
                Customer.objects.filter(pk=lead.customer_id).update(do_not_contact=True)
            LeadVisit.objects.create(
                lead=locked, salesperson=request.user, outcome=locked.status, notes=form.cleaned_data.get("notes", "")
            )
            audit(request.user, "lead.updated", locked, {"from_status": old_status, "to_status": locked.status})
        messages.success(request, "Lead updated and activity recorded.")
        return redirect("operations:lead_detail", pk=lead.pk)
    return page(request, "lead_detail.html", lead.customer.name, "leads", lead=lead, form=form)


@staff_required
def estimate_list(request):
    selling_required(request.user)
    return page(
        request,
        "estimates.html",
        "Estimates",
        "estimates",
        estimates=services.estimates_for(request.user).select_related("customer", "property")[:100],
    )


@staff_required
def estimate_create(request, pk):
    selling_required(request.user)
    lead = get_object_or_404(services.leads_for(request.user), pk=pk)
    form = forms.EstimateForm(request.POST or None)
    line_forms = forms.EstimateLineFormSet(request.POST or None, prefix="lines")
    if request.method == "POST" and form.is_valid() and line_forms.is_valid():
        lines = [
            f.cleaned_data
            for f in line_forms
            if not f.cleaned_data.get("DELETE")
            and (f.cleaned_data.get("price_book_item") or f.cleaned_data.get("description"))
        ]
        if not lines:
            form.add_error(None, "Choose at least one service and quantity.")
        else:
            try:
                estimate = services.create_estimate(actor=request.user, lead=lead, lines=lines, **form.cleaned_data)
                messages.success(request, "Estimate created. Review it before sending.")
                return redirect("operations:estimate_detail", pk=estimate.pk)
            except ValidationError as error:
                errors(form, error)
    return page(
        request, "estimate_form.html", "Build an estimate", "estimates", lead=lead, form=form, line_forms=line_forms
    )


@staff_required
def estimate_detail(request, pk):
    selling_required(request.user)
    estimate = get_object_or_404(services.estimates_for(request.user).select_related("customer", "property"), pk=pk)
    share_link = request.session.pop("estimate_link_" + str(pk), "")
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "approve":
                services.approve_estimate(actor=request.user, estimate=estimate)
                messages.success(request, "Pricing approved. The estimate is ready to send.")
            elif action == "send":
                token = services.send_estimate(actor=request.user, estimate=estimate)
                share_link = request.build_absolute_uri(reverse("portal:estimate", kwargs={"token": token}))
                request.session["estimate_link_" + str(pk)] = share_link
                messages.success(request, "Estimate delivery queued. You can also copy the secure link below.")
            elif action == "revoke":
                services.require_admin(request.user)
                with transaction.atomic():
                    locked = type(estimate).objects.select_for_update().get(pk=pk)
                    locked.public_token_version += 1
                    locked.save(update_fields=["public_token_version"])
                    audit(request.user, "estimate.links_revoked", locked)
                messages.success(request, "Previous customer links revoked.")
            else:
                raise ValidationError("Choose a valid estimate action.")
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        return redirect("operations:estimate_detail", pk=pk)
    return page(request, "estimate_detail.html", estimate.number, "estimates", estimate=estimate, share_link=share_link)


@staff_required
def estimate_revise(request, pk):
    selling_required(request.user)
    original = get_object_or_404(services.estimates_for(request.user), pk=pk)
    initial = {
        name: getattr(original, name) for name in ["discount", "tax_rate", "expires_on", "customer_notes", "terms"]
    }
    if initial["expires_on"] and initial["expires_on"] < timezone.localdate():
        initial["expires_on"] = timezone.localdate() + timezone.timedelta(days=30)
    form = forms.EstimateRevisionForm(request.POST if request.method == "POST" else None, initial=initial)
    initial_lines = [
        {
            "price_book_item": line.price_book_item_id,
            "quantity": line.quantity,
            "unit_price": line.unit_price,
            "description": line.description,
            "unit": line.unit,
        }
        for line in original.lines.all()
    ]
    line_forms = forms.EstimateLineFormSet(
        request.POST if request.method == "POST" else None, prefix="lines", initial=initial_lines
    )
    if request.method == "POST" and form.is_valid() and line_forms.is_valid():
        lines = [
            f.cleaned_data
            for f in line_forms
            if not f.cleaned_data.get("DELETE")
            and (f.cleaned_data.get("price_book_item") or f.cleaned_data.get("description"))
        ]
        try:
            revised = services.create_estimate(
                actor=request.user, lead=original.lead, supersedes=original, lines=lines, **form.cleaned_data
            )
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(
                request,
                "Revision created. The old estimate and links are retired. Review and send the replacement for customer approval.",
            )
            return redirect("operations:estimate_detail", pk=revised.pk)
    return page(
        request,
        "estimate_form.html",
        "Revise " + original.number,
        "estimates",
        lead=original.lead,
        form=form,
        line_forms=line_forms,
        original=original,
    )


@staff_required
def book_job(request, pk):
    selling_required(request.user)
    estimate = get_object_or_404(services.estimates_for(request.user), pk=pk)
    form = forms.ScheduleForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            job = services.schedule_job(actor=request.user, estimate=estimate, **form.cleaned_data)
            messages.success(request, "Appointment booked. The job is ready for assignment.")
            return redirect("operations:job_detail", pk=job.pk)
        except ValidationError as error:
            errors(form, error)
    occupied = (
        Job.objects.filter(scheduled_end__gte=timezone.now())
        .exclude(status="canceled")
        .values("scheduled_start", "scheduled_end")[:30]
    )
    return page(
        request,
        "form.html",
        "Schedule approved work",
        "schedule",
        form=form,
        form_description=str(estimate.customer) + " · " + estimate.number,
        submit_label="Confirm appointment",
        occupied=occupied,
    )


@staff_required
def customer_list(request):
    selling_required(request.user)
    records = services.customers_for(request.user).prefetch_related("properties")
    query = request.GET.get("q", "").strip()
    if query:
        records = records.filter(Q(name__icontains=query) | Q(email__icontains=query))
    return page(request, "customers.html", "Customers & properties", "customers", customers=records[:100], query=query)


@admin_required
def customer_create(request):
    form = forms.CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            customer = form.save()
            audit(request.user, "customer.created", customer)
        return redirect("operations:customer_detail", pk=customer.pk)
    return page(request, "form.html", "New customer", "customers", form=form, submit_label="Create customer")


@staff_required
def customer_detail(request, pk):
    selling_required(request.user)
    customer = get_object_or_404(services.customers_for(request.user), pk=pk)
    return page(
        request,
        "customer_detail.html",
        customer.name,
        "customers",
        customer=customer,
        jobs=services.jobs_for(request.user).filter(customer=customer),
        customer_leads=services.leads_for(request.user).filter(customer=customer),
    )


@admin_required
def customer_related(request, pk, kind):
    customer = get_object_or_404(Customer, pk=pk)
    if kind not in ["property", "contact"]:
        raise Http404
    form = (forms.PropertyForm if kind == "property" else forms.ContactForm)(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            record = form.save(commit=False)
            record.customer = customer
            record.save()
            audit(request.user, kind + ".created", record)
        return redirect("operations:customer_detail", pk=pk)
    return page(
        request,
        "form.html",
        "Add " + kind,
        "customers",
        form=form,
        form_description=customer.name,
        submit_label="Save " + kind,
    )


@staff_required
def schedule(request):
    jobs = services.jobs_for(request.user).select_related("customer", "property").exclude(status="canceled")
    if request.GET.get("range") != "all":
        jobs = jobs.filter(scheduled_end__gte=timezone.now() - timezone.timedelta(days=1))
    return page(
        request,
        "schedule.html",
        "The schedule",
        "schedule",
        jobs=jobs[:100],
        blocks=AvailabilityBlock.objects.filter(ends_at__gte=timezone.now())[:30]
        if services.is_admin(request.user)
        else [],
        recurring=RecurringPlan.objects.all() if services.is_admin(request.user) else [],
    )


@admin_required
def schedule_block(request):
    form = forms.AvailabilityForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from .planning import save_block

        try:
            save_block(actor=request.user, values=form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Unavailable time added.")
            return redirect("operations:schedule")
    return page(
        request, "form.html", "Block unavailable time", "schedule", form=form, submit_label="Save unavailable time"
    )


@staff_required
def job_list(request):
    jobs = services.jobs_for(request.user).select_related("customer", "property")
    if request.GET.get("status"):
        jobs = jobs.filter(status=request.GET["status"])
    offers = JobOffer.objects.select_related("job__customer", "job__property", "cleaner")
    if not services.is_admin(request.user):
        offers = offers.filter(cleaner=request.user)
    return page(
        request,
        "jobs.html",
        "Jobs & offers",
        "jobs",
        jobs=jobs[:100],
        offers=offers.filter(status="offered"),
        statuses=Job.Status.choices,
    )


@staff_required
def job_detail(request, pk):
    job = get_object_or_404(services.jobs_for(request.user).select_related("customer", "property", "estimate"), pk=pk)
    own_offers = job.offers.filter(cleaner=request.user)
    can_work = own_offers.filter(status="accepted").exists() or services.is_admin(request.user)
    if request.method == "POST":
        try:
            action = request.POST.get("action", "")
            if action in ["approve", "return"]:
                services.approve_completion(
                    actor=request.user, job=job, approved=action == "approve", reason=request.POST.get("notes", "")
                )
            elif action == "status":
                services.transition_job(
                    actor=request.user,
                    job=job,
                    status=request.POST.get("status", ""),
                    notes=request.POST.get("notes", ""),
                    completed_checklist=request.POST.getlist("checklist"),
                )
            elif action == "photo":
                # Job evidence has a private storage and an authenticated retrieval endpoint.
                from portal.evidence import add_evidence

                add_evidence(request.user, job, request.FILES.get("photo"), request.POST.get("caption", ""))
            else:
                raise ValidationError("Choose a valid job action.")
            messages.success(request, "Job updated.")
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        return redirect("operations:job_detail", pk=pk)
    next_states = {
        "confirmed": [("en_route", "On my way")],
        "en_route": [("arrived", "I have arrived")],
        "arrived": [("in_progress", "Start work")],
        "in_progress": [("completion_submitted", "Submit completion")],
        "issue": [("in_progress", "Resume work")],
    }.get(job.status, [])
    return page(
        request,
        "job_detail.html",
        job.number,
        "jobs",
        job=job,
        offers=job.offers.all() if services.is_admin(request.user) else own_offers,
        can_work=can_work,
        next_states=next_states,
        can_reschedule=services.is_admin(request.user) and job.status in ["scheduled", "offered", "confirmed"],
        can_cancel=services.is_admin(request.user) and job.status not in ["completed", "canceled"],
    )


@admin_required
def job_reschedule(request, pk):
    job = get_object_or_404(Job.objects.select_related("customer", "property"), pk=pk)
    form = forms.RescheduleForm(
        request.POST if request.method == "POST" else None,
        initial={"scheduled_start": job.scheduled_start, "scheduled_end": job.scheduled_end},
    )
    if request.method == "POST" and form.is_valid():
        try:
            services.reschedule_job(actor=request.user, job=job, **form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Appointment changed. Send new job offers so cleaners can accept the new time.")
            return redirect("operations:job_detail", pk=pk)
    return page(
        request,
        "job_change.html",
        "Reschedule appointment",
        "schedule",
        job=job,
        form=form,
        explanation="Changing the appointment retires current offers and pending pay agreements. "
        "Send new offers after saving; each cleaner must accept the new schedule.",
        submit_label="Save new appointment",
        back_url=reverse("operations:job_detail", kwargs={"pk": pk}),
    )


@admin_required
def job_cancel(request, pk):
    job = get_object_or_404(Job.objects.select_related("customer", "property"), pk=pk)
    form = forms.ChangeReasonForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.cancel_job(actor=request.user, job=job, **form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Job canceled. Active offers were withdrawn and the history was retained.")
            return redirect("operations:job_detail", pk=pk)
    return page(
        request,
        "job_change.html",
        "Cancel appointment",
        "schedule",
        job=job,
        form=form,
        explanation="This releases the appointment and withdraws active cleaner offers. "
        "Pending pay agreements are reversed. The job and its history remain available.",
        submit_label="Cancel appointment",
        destructive=True,
        back_url=reverse("operations:job_detail", kwargs={"pk": pk}),
    )


@admin_required
def offer_withdraw(request, pk):
    offer = get_object_or_404(JobOffer.objects.select_related("job__customer", "job__property", "cleaner"), pk=pk)
    form = forms.ChangeReasonForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            services.withdraw_offer(actor=request.user, offer=offer, **form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Offer withdrawn. You can now offer this crew slot again.")
            return redirect("operations:job_detail", pk=offer.job_id)
    return page(
        request,
        "job_change.html",
        "Withdraw job offer",
        "jobs",
        job=offer.job,
        offer=offer,
        form=form,
        explanation="The cleaner will see that this offer was withdrawn. Any pending pay agreement is reversed; "
        "the original offer and accepted terms remain in the history.",
        submit_label="Withdraw offer",
        destructive=True,
        back_url=reverse("operations:offer_detail", kwargs={"pk": pk}),
    )


@admin_required
def offer_create(request, pk):
    job = get_object_or_404(Job, pk=pk)
    form = forms.OfferForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.offer_job(actor=request.user, job=job, **form.cleaned_data)
            messages.success(request, "Fixed-pay offer sent to the cleaner’s inbox.")
            return redirect("operations:job_detail", pk=pk)
        except ValidationError as error:
            errors(form, error)
    return page(
        request,
        "form.html",
        "Offer this job",
        "jobs",
        form=form,
        form_description=f"{job.customer} · {job.scheduled_start:%b %d}. The cleaner must accept these exact terms.",
        submit_label="Send job offer",
    )


@staff_required
def offer_detail(request, pk):
    queryset = JobOffer.objects.select_related("job__customer", "job__property", "cleaner")
    if not services.is_admin(request.user):
        queryset = queryset.filter(cleaner=request.user)
    offer = get_object_or_404(queryset, pk=pk)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action not in ["accept", "reject"]:
                raise ValidationError("Choose accept or reject.")
            services.respond_to_offer(
                actor=request.user, offer=offer, accept=action == "accept", reason=request.POST.get("reason", "")
            )
            messages.success(
                request,
                "Offer accepted. These terms are saved."
                if action == "accept"
                else "Offer declined. The office has been notified.",
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        return redirect("operations:offer_detail", pk=pk)
    return page(request, "offer_detail.html", "Your job offer", "jobs", offer=offer)


@admin_required
def invoice_list(request):
    return page(
        request,
        "invoices.html",
        "Invoices",
        "invoices",
        invoices=Invoice.objects.select_related("customer", "job")[:100],
    )


@admin_required
def invoice_create(request, pk):
    job = get_object_or_404(Job.objects.select_related("customer", "estimate"), pk=pk)
    form = forms.InvoiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            invoice = services.issue_invoice(actor=request.user, job=job, **form.cleaned_data)
            messages.success(request, "Invoice issued from the approved estimate. Its amounts are preserved.")
            return redirect("operations:invoice_detail", pk=invoice.pk)
        except ValidationError as error:
            errors(form, error)
    return page(
        request,
        "form.html",
        "Issue an invoice",
        "invoices",
        form=form,
        form_description=f"{job.customer} · Approved scope {job.estimate.number} · ${job.estimate.total}",
        submit_label="Issue invoice",
        document=job.estimate,
    )


@admin_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("customer", "job__property"), pk=pk)
    form = forms.PaymentForm(
        request.POST if request.POST.get("action") == "payment" else None,
        initial={"amount": invoice.balance, "idempotency_key": uuid.uuid4()},
    )
    share_link = request.session.pop("invoice_link_" + str(pk), "")
    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "payment" and form.is_valid():
                values = form.cleaned_data.copy()
                values["idempotency_key"] = str(values["idempotency_key"])
                services.record_payment(actor=request.user, invoice=invoice, **values)
                messages.success(request, "Payment recorded and balance updated.")
                return redirect("operations:invoice_detail", pk=pk)
            elif action == "link":
                from portal.services import invoice_token

                token = invoice_token(invoice, actor=request.user)
                request.session["invoice_link_" + str(pk)] = request.build_absolute_uri(
                    reverse("portal:invoice", kwargs={"token": token})
                )
                return redirect("operations:invoice_detail", pk=pk)
            elif action == "reverse":
                payment = get_object_or_404(Payment, pk=request.POST.get("payment"), invoice=invoice)
                services.reverse_payment(actor=request.user, payment=payment, reason=request.POST.get("reason", ""))
                messages.success(request, "Reversal recorded. The original payment remains in the ledger.")
                return redirect("operations:invoice_detail", pk=pk)
            elif action == "void":
                services.void_invoice(actor=request.user, invoice=invoice, reason=request.POST.get("reason", ""))
                messages.success(request, "Invoice voided. Its history is retained.")
                return redirect("operations:invoice_detail", pk=pk)
            elif action == "send":
                services.send_invoice(actor=request.user, invoice=invoice)
                messages.success(request, "Invoice email queued.")
                return redirect("operations:invoice_detail", pk=pk)
            elif action != "payment":
                raise ValidationError("Choose a valid invoice action.")
        except ValidationError as error:
            errors(form, error)
    return page(
        request,
        "invoice_detail.html",
        invoice.number or "Draft invoice",
        "invoices",
        invoice=invoice,
        form=form,
        share_link=share_link,
    )


@staff_required
def compensation(request):
    commissions = CommissionEntry.objects.select_related("salesperson", "invoice")
    payouts = CleanerPayout.objects.select_related("cleaner", "offer__job")
    if not services.is_admin(request.user):
        commissions = commissions.filter(salesperson=request.user)
        payouts = payouts.filter(cleaner=request.user)
    if request.method == "POST":
        services.require_admin(request.user)
        try:
            if request.POST.get("kind") == "commission":
                services.mark_commission_paid(
                    actor=request.user,
                    entry=get_object_or_404(commissions, pk=request.POST.get("entry")),
                    reference=request.POST.get("reference", ""),
                )
            elif request.POST.get("kind") == "payout":
                services.mark_payout_paid(
                    actor=request.user,
                    payout=get_object_or_404(payouts, pk=request.POST.get("entry")),
                    reference=request.POST.get("reference", ""),
                )
            else:
                raise ValidationError("Choose a valid ledger.")
            messages.success(request, "Payout recorded. No funds were transferred by the platform.")
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        return redirect("operations:compensation")
    return page(
        request,
        "compensation.html",
        "Compensation" if services.is_admin(request.user) else "My earnings",
        "compensation",
        commissions=commissions[:100],
        payouts=payouts[:100],
    )


@staff_required
def notifications(request):
    records = Notification.objects.filter(recipient=request.user)
    if request.method == "POST":
        records.filter(read_at__isnull=True).update(read_at=timezone.now())
        messages.success(request, "Your notifications are marked as read.")
        return redirect("operations:notifications")
    return page(request, "notifications.html", "Your inbox", "notifications", notifications=records[:100])


@admin_required
def price_book(request):
    return page(request, "price_book.html", "Price book", "price_book", items=PriceBookItem.objects.all())


@admin_required
def price_book_edit(request, pk=None):
    item = get_object_or_404(PriceBookItem, pk=pk) if pk else None
    form = forms.PriceBookForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        item = form.save()
        audit(request.user, "pricebook.updated" if pk else "pricebook.created", item)
        messages.success(request, "Price book saved. Existing estimates keep their original rates.")
        return redirect("operations:price_book")
    return page(
        request,
        "form.html",
        "Edit service pricing" if pk else "Add service pricing",
        "price_book",
        form=form,
        submit_label="Save service",
    )


@admin_required
def recurring_create(request, pk):
    job = get_object_or_404(Job, pk=pk)
    form = forms.RecurringForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        plan = form.save(commit=False)
        plan.customer, plan.property, plan.estimate = job.customer, job.property, job.estimate
        from .planning import save_plan

        try:
            save_plan(actor=request.user, plan=plan, values=form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(
                request,
                "Recurring plan saved. Generate the next visit from Schedule or use the configured background scheduler.",
            )
            return redirect("operations:schedule")
    return page(
        request,
        "form.html",
        "Create recurring service",
        "schedule",
        form=form,
        form_description=job.customer.name,
        submit_label="Save recurring plan",
    )


@admin_required
def reports(request):
    invoices = Invoice.objects.exclude(status__in=["void", "draft"])
    now = timezone.localdate()
    aging = {"Current": Decimal("0"), "1–30 days": Decimal("0"), "31–60 days": Decimal("0"), "61+ days": Decimal("0")}
    for invoice in invoices:
        days = (now - invoice.due_date).days
        key = "Current" if days <= 0 else "1–30 days" if days <= 30 else "31–60 days" if days <= 60 else "61+ days"
        aging[key] += invoice.balance
    return page(
        request,
        "reports.html",
        "Business reports",
        "reports",
        lead_sources=Lead.objects.values("source").annotate(count=Count("id")).order_by("-count"),
        lead_states=Lead.objects.values("status").annotate(count=Count("id")),
        estimate_states=services.estimates_for(request.user).values("status").annotate(count=Count("id")),
        aging=aging.items(),
        collected=Payment.objects.aggregate(total=Sum("amount"))["total"] or 0,
        booked=services.estimates_for(request.user).filter(status="accepted").aggregate(total=Sum("total"))["total"]
        or 0,
        assignments=JobOffer.objects.values("status").annotate(count=Count("id")),
    )


@admin_required
def audit_log(request):
    return page(
        request, "audit.html", "Audit history", "audit", events=AuditEvent.objects.select_related("actor")[:150]
    )
