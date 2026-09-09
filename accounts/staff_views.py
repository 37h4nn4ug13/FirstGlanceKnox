from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from operations.models import AuditEvent, JobOffer, Lead
from operations.views import page
from .forms import InvitationForm, StaffEditForm
from .models import StaffProfile, User
from .permissions import admin_required
from . import services, staff_services


def deliver(request, invitation):
    try:
        services.email_invitation(invitation, request)
    except Exception:
        messages.error(
            request, "The invitation was saved, but email delivery failed. Use Send new invitation to retry."
        )
    else:
        messages.success(
            request,
            "Invitation created through the configured email backend. Local preview email stays on this computer.",
        )


@admin_required
def staff_list(request):
    profiles = (
        StaffProfile.objects.select_related("user").prefetch_related("user__groups").order_by("display_name", "pk")
    )
    query = request.GET.get("q", "").strip()
    state = request.GET.get("state", "")
    if query:
        profiles = profiles.filter(Q(display_name__icontains=query) | Q(user__email__icontains=query))
    if state in ["active", "invited", "inactive"]:
        profiles = profiles.filter(onboarding_state=state)
    return page(request, "staff_list.html", "Your team", "staff", profiles=profiles, query=query, selected_state=state)


@admin_required
def staff_invite(request):
    form = InvitationForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            invitation = services.invite_staff(actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            deliver(request, invitation)
            return redirect("accounts:staff_detail", public_id=invitation.user.public_id)
    return page(
        request,
        "form.html",
        "Invite an employee",
        "staff",
        form=form,
        submit_label="Create invitation",
        form_description="Choose the employee’s roles. They will set their own password using a three-day invitation.",
    )


@admin_required
def staff_detail(request, public_id):
    employee = get_object_or_404(
        User.objects.select_related("staff_profile"), public_id=public_id, staff_profile__isnull=False
    )
    profile = employee.staff_profile
    form = StaffEditForm(
        request.POST if request.method == "POST" else None,
        initial={
            "display_name": profile.display_name,
            "phone": profile.phone,
            "skills": profile.skills,
            "internal_notes": profile.internal_notes,
            "default_commission_rate": profile.default_commission_rate,
            "roles": list(employee.groups.values_list("name", flat=True)),
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            staff_services.update_staff(actor=request.user, user=employee, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request, "Employee updated. Existing accepted estimates and pay agreements retain their saved amounts."
            )
            return redirect("accounts:staff_detail", public_id=public_id)
    return page(
        request,
        "staff_detail.html",
        profile.display_name,
        "staff",
        employee=employee,
        profile=profile,
        form=form,
        offers=JobOffer.objects.filter(cleaner=employee, status__in=["offered", "accepted"]).select_related("job"),
        leads=Lead.objects.filter(assigned_to=employee).exclude(status__in=["won", "lost", "do_not_contact"]),
        invitations=employee.invitations.order_by("-created_at")[:5],
        events=AuditEvent.objects.filter(object_id=employee.public_id).select_related("actor")[:15],
    )


@admin_required
def staff_deactivate(request, public_id):
    from operations.forms import ChangeReasonForm

    employee = get_object_or_404(User, public_id=public_id, staff_profile__isnull=False)
    form = ChangeReasonForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            staff_services.deactivate_staff(actor=request.user, user=employee, **form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
        else:
            messages.success(
                request,
                "Access deactivated. Review unassigned leads and active jobs for handoff. Historical records were preserved.",
            )
            return redirect("accounts:staff_detail", public_id=public_id)
    return page(request, "staff_deactivate.html", "Deactivate employee access", "staff", employee=employee, form=form)


@admin_required
@require_POST
def staff_reinvite(request, public_id):
    employee = get_object_or_404(User, public_id=public_id, staff_profile__isnull=False)
    try:
        invitation = staff_services.renew_invitation(actor=request.user, user=employee)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        deliver(request, invitation)
    return redirect("accounts:staff_detail", public_id=public_id)


@admin_required
@require_POST
def invitation_revoke(request, public_id):
    from .models import StaffInvitation

    invitation = get_object_or_404(StaffInvitation, public_id=public_id)
    try:
        staff_services.revoke_invitation(actor=request.user, invitation=invitation)
    except ValidationError as error:
        messages.error(request, " ".join(error.messages))
    else:
        messages.success(request, "Invitation revoked.")
    return redirect(reverse("accounts:staff_detail", kwargs={"public_id": invitation.user.public_id}))
