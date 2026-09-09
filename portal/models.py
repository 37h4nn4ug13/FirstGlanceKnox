import uuid
from pathlib import Path
from django.conf import settings
from django.db import models
from marketing.models import PrivateMediaStorage


def evidence_path(instance, filename):
    return f"evidence/{instance.job_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class JobEvidence(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey("operations.Job", on_delete=models.PROTECT, related_name="evidence")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    image = models.ImageField(storage=PrivateMediaStorage(), upload_to=evidence_path)
    caption = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
