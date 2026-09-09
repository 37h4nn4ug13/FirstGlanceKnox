import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.views import LoginView
from django.core import signing
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import EmailAuthenticationForm, NotificationPreferenceForm, ProfileForm
from .models import NotificationPreference, PushSubscription, StaffInvitation
from .permissions import has_role, staff_required
from .services import (
    accept_invitation,
    invitation_from_token,
    push_configuration,
    validate_push_endpoint,
)


class AccountLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return "/crew/" if has_role(self.request.user, "Admin", "Salesperson", "Cleaner") else "/portal/"


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        PushSubscription.objects.filter(user=request.user, active=True).update(active=False)
    logout(request)
    response = render(request, "accounts/logged_out.html")
    response["Cache-Control"] = "no-store"
    response["Clear-Site-Data"] = '"cache", "storage"'
    return response


@login_required
def profile(request):
    preferences, _ = NotificationPreference.objects.get_or_create(user=request.user)
    form = ProfileForm(request.POST or None, instance=request.user)
    preference_form = NotificationPreferenceForm(
        request.POST or None, initial={"email_enabled": preferences.email_enabled}
    )
    if request.method == "POST" and form.is_valid() and preference_form.is_valid():
        form.save()
        preferences.email_enabled = preference_form.cleaned_data["email_enabled"]
        preferences.save(update_fields=["email_enabled"])
        messages.success(request, "Your preferences were saved.")
        return redirect("accounts:profile")
    return render(
        request,
        "accounts/profile.html",
        {
            "form": form,
            "preference_form": preference_form,
            "subscriptions": PushSubscription.objects.filter(user=request.user, active=True),
            "push_config": push_configuration(),
            "staff_account": has_role(request.user, "Admin", "Salesperson", "Cleaner"),
        },
    )


def invitation_accept(request, token):
    try:
        invitation = invitation_from_token(token)
    except (signing.BadSignature, StaffInvitation.DoesNotExist, ValueError, KeyError):
        return render(request, "accounts/invitation_expired.html", status=410)
    form = SetPasswordForm(invitation.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            accept_invitation(token=token, password=form.cleaned_data["new_password1"])
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Your account is ready. Sign in with your new password.")
            return redirect("accounts:login")
    return render(request, "accounts/accept_invitation.html", {"form": form, "invitation": invitation})


@staff_required
@require_GET
def session_info(request):
    from django.middleware.csrf import get_token

    response = JsonResponse(
        {
            "user": str(request.user.public_id),
            "csrf": get_token(request),
            "push": push_configuration(),
            "roles": list(request.user.groups.values_list("name", flat=True)),
        }
    )
    response["Cache-Control"] = "no-store"
    return response


@staff_required
@require_POST
def subscribe_push(request):
    if not push_configuration()["enabled"]:
        return JsonResponse(
            {
                "error": "Push notifications are not configured. Your updates remain available in the notification center."
            },
            status=409,
        )
    try:
        data = json.loads(request.body)
        endpoint = data["endpoint"]
        validate_push_endpoint(endpoint)
        p256dh, auth = data["keys"]["p256dh"], data["keys"]["auth"]
        if (
            not isinstance(p256dh, str)
            or not isinstance(auth, str)
            or not 20 <= len(p256dh) <= 256
            or not 8 <= len(auth) <= 256
        ):
            raise ValueError
        PushSubscription.objects.update_or_create(
            endpoint=endpoint,
            defaults={
                "user": request.user,
                "p256dh": p256dh,
                "auth": auth,
                "active": True,
                "device_name": str(data.get("device_name", "This browser"))[:120],
            },
        )
        NotificationPreference.objects.update_or_create(user=request.user, defaults={"push_enabled": True})
    except (ValueError, KeyError, TypeError, ValidationError):
        return JsonResponse({"error": "A valid browser subscription is required."}, status=400)
    return JsonResponse({"ok": True})


@staff_required
@require_POST
def unsubscribe_push(request, subscription_id):
    PushSubscription.objects.filter(pk=subscription_id, user=request.user).update(active=False)
    messages.success(request, "Device notifications disabled.")
    return redirect("accounts:profile")


@require_GET
def crew_manifest(request):
    return JsonResponse(
        {
            "id": "/crew/",
            "name": "FirstGlanceKnox Crew",
            "short_name": "FGK Crew",
            "description": "Your FirstGlanceKnox workday, in one place.",
            "start_url": "/crew/",
            "scope": "/crew/",
            "display": "standalone",
            "background_color": "#f6f8f9",
            "theme_color": "#12252b",
            "icons": [
                {"src": "/static/crew/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/static/crew/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            ],
        },
        content_type="application/manifest+json",
    )


@require_GET
def crew_service_worker(request):
    source = settings.BASE_DIR / "static" / "crew" / "sw.js"
    response = HttpResponse(source.read_text(encoding="utf-8"), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/crew/"
    response["Cache-Control"] = "no-cache"
    return response
