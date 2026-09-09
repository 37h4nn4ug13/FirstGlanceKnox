from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from . import forms, planning, services
from .models import AvailabilityBlock, OutboundMessage, RecurringPlan
from .views import admin_required, errors, page


@admin_required
def block_edit(request, pk):
    block = get_object_or_404(AvailabilityBlock, pk=pk)
    form = forms.AvailabilityForm(request.POST if request.method == "POST" else None, instance=block)
    if request.method == "POST" and form.is_valid():
        try:
            planning.save_block(actor=request.user, block=block, values=form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Unavailable time updated.")
            return redirect("operations:schedule")
    return page(
        request, "form.html", "Edit unavailable time", "schedule", form=form, submit_label="Save unavailable time"
    )


@admin_required
def block_remove(request, pk):
    block = get_object_or_404(AvailabilityBlock, pk=pk)
    form = forms.ChangeReasonForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            planning.remove_block(actor=request.user, block=block, **form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(request, "Unavailable time removed. The change remains in audit history.")
            return redirect("operations:schedule")
    return page(
        request,
        "form.html",
        "Remove unavailable time",
        "schedule",
        form=form,
        form_description=f"{block.staff or 'Whole business'} · {block.starts_at:%b %d, %Y}. Removing a block makes this time available for booking.",
        submit_label="Remove block",
    )


@admin_required
def plan_edit(request, pk):
    plan = get_object_or_404(RecurringPlan, pk=pk)
    form = forms.RecurringEditForm(request.POST if request.method == "POST" else None, instance=plan)
    if request.method == "POST" and form.is_valid():
        try:
            planning.save_plan(actor=request.user, plan=plan, values=form.cleaned_data)
        except ValidationError as error:
            errors(form, error)
        else:
            messages.success(
                request,
                "Recurring plan updated. Existing appointments are unchanged; manage those from their job pages.",
            )
            return redirect("operations:schedule")
    return page(
        request,
        "form.html",
        "Edit recurring service",
        "schedule",
        form=form,
        submit_label="Save recurring plan",
        form_description="Uncheck Active to pause future generation. To resume an overdue plan, choose a future next visit. Existing jobs keep their appointments.",
    )


@admin_required
@require_POST
def plan_generate(request, pk):
    plan = get_object_or_404(RecurringPlan, pk=pk)
    try:
        from django.utils.dateparse import parse_datetime

        try:
            expected = parse_datetime(request.POST.get("expected_visit", ""))
        except ValueError:
            expected = None
        if expected is None or expected.tzinfo is None:
            raise ValidationError("Refresh the schedule before generating this visit.")
        job = services.generate_recurring_visit(actor=request.user, plan=plan, expected_visit=expected)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
        return redirect("operations:schedule")
    messages.success(request, "Next visit booked. Send cleaner offers to staff the appointment.")
    return redirect("operations:job_detail", pk=job.pk)


@admin_required
def deliveries(request):
    records = OutboundMessage.objects.all()
    state = request.GET.get("state", "pending")
    records = records.filter(sent_at__isnull=state != "sent")
    return page(request, "deliveries.html", "Email deliveries", "deliveries", deliveries=records[:100], state=state)


@admin_required
@require_POST
def delivery_retry(request, pk):
    from .tasks import deliver_message

    message = get_object_or_404(OutboundMessage, pk=pk)
    result = deliver_message(str(message.pk))
    if result in ["sent", "already_sent"]:
        messages.success(
            request,
            "Delivery recorded through the configured email backend. Local preview email is saved on this computer.",
        )
    elif result == "obsolete":
        messages.warning(
            request, "This message belongs to an outdated or revoked document. Send the current document instead."
        )
    else:
        messages.error(request, "Delivery failed. Check the email configuration before retrying.")
    services._audit(request.user, "email.delivery_requested", message, result=result)
    return redirect("operations:deliveries")
