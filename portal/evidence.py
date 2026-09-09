from io import BytesIO
from PIL import Image, UnidentifiedImageError
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from accounts.permissions import staff_required
from operations import services
from .models import JobEvidence


@transaction.atomic
def add_evidence(actor, job, upload, caption=""):
    if not services.is_admin(actor) and not job.offers.filter(cleaner=actor, status="accepted").exists():
        raise PermissionDenied
    if job.status in ["completed", "canceled"]:
        raise ValidationError("This job no longer accepts evidence uploads.")
    if not upload or upload.size > 10 * 1024 * 1024:
        raise ValidationError("Choose a JPEG, PNG, or WebP image up to 10 MB.")
    try:
        with Image.open(upload) as source:
            if source.format not in ["JPEG", "PNG", "WEBP"] or source.width * source.height > 40_000_000:
                raise ValidationError("This image format or size is not supported.")
            source.load()
            image = source.convert("RGB")
            image.thumbnail((2400, 2400))
            output = BytesIO()
            image.save(output, "JPEG", quality=88)  # Re-encode to strip embedded metadata.
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValidationError("The uploaded file is not a valid image.") from None
    evidence = JobEvidence(job=job, uploaded_by=actor, caption=str(caption)[:240])
    evidence.image.save("evidence.jpg", ContentFile(output.getvalue()), save=True)
    services._audit(actor, "job.evidence_added", job, evidence_id=str(evidence.pk))
    return evidence


@staff_required
def evidence_view(request, pk):
    evidence = get_object_or_404(
        JobEvidence.objects.select_related("job"), pk=pk, job__in=services.jobs_for(request.user)
    )
    if (
        not services.is_admin(request.user)
        and not evidence.job.offers.filter(cleaner=request.user, status__in=["accepted", "completed"]).exists()
    ):
        raise PermissionDenied
    response = FileResponse(evidence.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
