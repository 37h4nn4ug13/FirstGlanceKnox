from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from operations.models import Customer, Estimate, Invoice, Job
from .forms import EstimateDeclineForm, EstimateResponseForm, RepeatServiceForm
from .services import document_pdf


VISIBLE_ESTIMATE_STATES = ["sent", "viewed", "accepted", "declined", "expired", "superseded"]
VISIBLE_INVOICE_STATES = ["issued", "partial", "paid", "void"]


def _private(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    # Native POST forms need their same-origin Origin/Referer for Django CSRF.
    # Suppress the private document URL on cross-origin requests only.
    response["Referrer-Policy"] = "same-origin"
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


@login_required
@never_cache
def home(request):
    accounts = Customer.objects.filter(user=request.user, active=True)
    jobs = Job.objects.filter(customer__in=accounts).select_related("property")
    return _private(
        render(
            request,
            "portal/home.html",
            {
                "customers": accounts,
                "estimates": Estimate.objects.filter(
                    customer__in=accounts, status__in=VISIBLE_ESTIMATE_STATES
                ).select_related("property")[:15],
                "invoices": Invoice.objects.filter(
                    customer__in=accounts, status__in=VISIBLE_INVOICE_STATES
                ).select_related("job__property")[:15],
                "appointments": jobs.exclude(status__in=["completed", "canceled"]).filter(
                    scheduled_end__gte=timezone.now()
                ),
                "history": jobs.filter(status="completed").order_by("-scheduled_start")[:20],
            },
        )
    )


def _resolve_document(request, *, kind, token=None, pk=None):
    from operations.services import resolve_access_token

    model = Estimate if kind == "estimate" else Invoice
    if token:
        try:
            result = resolve_access_token(token, kind)
        except (ValidationError, PermissionDenied, ValueError, model.DoesNotExist):
            raise Http404("This document link is unavailable.") from None
        # The domain API returns the document, not a grant to any adjacent records.
        document = result
    else:
        if not request.user.is_authenticated:
            raise PermissionDenied
        document = get_object_or_404(
            model.objects.select_related("customer"), pk=pk, customer__user=request.user, customer__active=True
        )
    visible = VISIBLE_ESTIMATE_STATES if kind == "estimate" else VISIBLE_INVOICE_STATES
    if document.status not in visible:
        raise Http404("This document is not available.")
    return document


@never_cache
def estimate(request, token=None, pk=None):
    from operations.services import accept_estimate, decline_estimate

    document = _resolve_document(request, kind="estimate", token=token, pk=pk)
    response_form = EstimateResponseForm(
        request.POST if request.method == "POST" and request.POST.get("action") == "accept" else None
    )
    decline_form = EstimateDeclineForm(
        request.POST if request.method == "POST" and request.POST.get("action") == "decline" else None
    )
    actor = request.user if request.user.is_authenticated else None
    if request.method == "POST":
        action = request.POST.get("action")
        selected_form = response_form if action == "accept" else decline_form
        if action not in ("accept", "decline"):
            selected_form.add_error(None, "Choose approve or decline.")
        elif selected_form.is_valid():
            try:
                if action == "accept":
                    accept_estimate(
                        actor=actor, estimate=document, signature=response_form.cleaned_data["signature"], token=token
                    )
                else:
                    decline_estimate(
                        actor=actor, estimate=document, reason=decline_form.cleaned_data["reason"], token=token
                    )
            except ValidationError as exc:
                selected_form.add_error(None, exc)
            else:
                messages.success(request, "Thank you. Your estimate response has been recorded.")
                return _private(
                    render(
                        request, "portal/response_received.html", {"accepted": action == "accept", "document": document}
                    )
                )
    can_respond = document.status in ("sent", "viewed") and (
        not document.expires_on or document.expires_on >= timezone.localdate()
    )
    return _private(
        render(
            request,
            "portal/estimate.html",
            {
                "document": document,
                "response_form": response_form,
                "decline_form": decline_form,
                "can_respond": can_respond,
                "token": token,
            },
        )
    )


@never_cache
def invoice(request, token=None, pk=None):
    document = _resolve_document(request, kind="invoice", token=token, pk=pk)
    return _private(
        render(
            request,
            "portal/invoice.html",
            {
                "document": document,
                "token": token,
                "payments": document.payments.order_by("received_at"),
                "payment_instructions": settings.PAYMENT_INSTRUCTIONS,
            },
        )
    )


@require_GET
@never_cache
def pdf(request, kind, token=None, pk=None):
    document = _resolve_document(request, kind=kind, token=token, pk=pk)
    response = HttpResponse(document_pdf(document, kind=kind), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="FirstGlanceKnox-{document.number}.pdf"'
    return _private(response)


@login_required
@never_cache
def repeat_service(request):
    form = RepeatServiceForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        from operations.services import create_repeat_lead

        create_repeat_lead(actor=request.user, property=form.cleaned_data["property"], notes=form.cleaned_data["notes"])
        messages.success(request, "Your service request has been received. We'll follow up to confirm details.")
        return redirect("portal:home")
    return _private(render(request, "portal/repeat_service.html", {"form": form}))
