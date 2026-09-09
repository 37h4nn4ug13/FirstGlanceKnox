import json
import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from .models import OfflineReceipt
from .permissions import staff_required
from operations import services


@staff_required
@require_GET
def summary(request):
    jobs = (
        services.jobs_for(request.user)
        .filter(scheduled_start__date__gte=timezone.localdate())
        .exclude(status="canceled")[:12]
    )
    return JsonResponse(
        {
            "user": str(request.user.public_id),
            "jobs": [
                {
                    "id": str(j.pk),
                    "number": j.number,
                    "start": j.scheduled_start.isoformat(),
                    "status": j.get_status_display(),
                }
                for j in jobs
            ],
        }
    )


@staff_required
@require_POST
@transaction.atomic
def sync(request):
    if len(request.body) > 16000:
        return JsonResponse({"error": "This update is too large."}, status=400)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
            raise ValidationError("This update has invalid fields. Review it in the device outbox.")
        if payload.get("user") != str(request.user.public_id):
            return JsonResponse({"error": "Sign in to the account that created this update."}, status=409)
        client_id = uuid.UUID(payload["id"])
        # One lock per user serializes duplicate sync requests even before receipt creation.
        from .models import User

        User.objects.select_for_update().get(pk=request.user.pk)
        existing = OfflineReceipt.objects.filter(user=request.user, client_id=client_id).first()
        if existing:
            return JsonResponse(existing.result)
        data = payload["data"]
        if payload["kind"] == "lead":
            from operations.forms import QuickLeadForm

            form = QuickLeadForm(data)
            if not form.is_valid():
                raise ValidationError("Review the lead fields before syncing.")
            fields = form.cleaned_data.copy()
            fields.pop("confirm_duplicate", None)
            fields["name"] = fields["name"] or "Prospect at " + fields["address"]
            lead = services.capture_lead(
                actor=request.user, source="door_to_door", idempotency_key=str(client_id), **fields
            )
            result = {"ok": True, "url": f"/crew/leads/{lead.pk}/"}
        elif payload["kind"] == "status":
            job = get_object_or_404(services.jobs_for(request.user), pk=data["job_id"])
            services.transition_job(
                actor=request.user,
                job=job,
                status=data["status"],
                notes=str(data.get("notes", ""))[:5000],
                completed_checklist=data.get("checklist", []),
            )
            result = {"ok": True, "url": f"/crew/jobs/{job.pk}/"}
        else:
            raise ValidationError("Unsupported offline update.")
        OfflineReceipt.objects.create(user=request.user, client_id=client_id, result=result)
        return JsonResponse(result)
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        return JsonResponse(
            {"error": "; ".join(exc.messages) if isinstance(exc, ValidationError) else "This update needs review."},
            status=409,
        )
