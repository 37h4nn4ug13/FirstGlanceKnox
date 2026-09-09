from io import BytesIO
from pathlib import Path

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import reverse
from PIL import Image

from marketing.media import publish_asset, unpublish_asset, validate_upload
from marketing.models import MediaAsset, Testimonial as Review, PrivateMediaStorage
from operations.models import Customer, Lead, Property

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_quote_limits():
    cache.clear()


def quote_data(**updates):
    return {
        "name": "Synthetic Quote Customer",
        "email": "quote@example.invalid",
        "phone": "865-555-0101",
        "address": "100 Synthetic Lane, Knoxville TN",
        "kind": "residential",
        "services": ["interior", "exterior"],
        "message": "Synthetic test quote",
        "consent": "on",
        **updates,
    }


@pytest.mark.parametrize(
    "name",
    ["home", "residential", "commercial", "gallery", "about", "areas", "quote", "contact", "faq", "privacy", "terms"],
)
def test_public_pages_render_and_use_original_logo(client, name):
    response = client.get(reverse("marketing:" + name))
    assert response.status_code == 200
    assert b"/static/brand/logo.jpg" in response.content
    assert b'id="main-content"' in response.content


def test_quote_creates_authoritative_crm_records(client):
    client.get(reverse("marketing:quote"))
    response = client.post(reverse("marketing:quote"), quote_data())
    assert response.status_code == 302
    assert response.url == reverse("marketing:quote_success")
    lead = Lead.objects.get()
    assert lead.customer.email == "quote@example.invalid"
    assert lead.property.customer == lead.customer
    assert lead.source == "website"
    assert lead.services == ["interior", "exterior"]
    assert Customer.objects.count() == Property.objects.count() == 1


def test_quote_honeypot_does_not_create_lead(client):
    response = client.post(reverse("marketing:quote"), quote_data(website="spam.invalid"))
    assert response.status_code == 302
    assert Lead.objects.count() == 0


def test_quote_validation_is_visible_and_preserves_values(client):
    response = client.post(reverse("marketing:quote"), quote_data(email="not-an-email"))
    assert response.status_code == 400
    assert b'role="alert"' in response.content
    assert b"Synthetic Quote Customer" in response.content
    assert not Lead.objects.exists()


def test_quote_rate_limit_blocks_expensive_work(client):
    for index in range(8):
        response = client.post(reverse("marketing:quote"), quote_data(message=f"Request {index}"))
        assert response.status_code == 302
    response = client.post(reverse("marketing:quote"), quote_data())
    assert response.status_code == 429
    assert Lead.objects.count() == 8


def test_gallery_never_exposes_private_media(client):
    MediaAsset.objects.create(
        title="Private customer evidence", alt_text="Never public", public_url="/private-evidence.jpg"
    )
    response = client.get(reverse("marketing:gallery"))
    assert b"Private customer evidence" not in response.content
    assert b"/private-evidence.jpg" not in response.content
    assert b"temporary images, not examples of our completed work" in response.content


def test_unverified_testimonial_is_not_public(client):
    Review.objects.create(
        name="Unverified person",
        quote="Unverified invented statement",
        published=True,
        verified=False,
        permission_to_publish=True,
    )
    assert b"Unverified invented statement" not in client.get("/").content


def test_database_rejects_publication_without_consent():
    with pytest.raises(IntegrityError), transaction.atomic():
        MediaAsset.objects.create(title="No consent", status="published", visibility="public", marketing_approved=False)


def test_upload_validation_checks_content():
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("fake.jpg", b"not an image", content_type="image/jpeg"))
    with pytest.raises(ValidationError):
        validate_upload(SimpleUploadedFile("fake.mp4", b"<script>bad</script>"), "video")


def test_consent_generates_responsive_files_and_unpublish_removes_them(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "public"
    original_field = MediaAsset._meta.get_field("original")
    prior_storage = original_field.storage
    original_field.storage = PrivateMediaStorage()
    original_field.storage._location = str(tmp_path / "private")
    try:
        output = BytesIO()
        Image.new("RGB", (1300, 900), "#88bbcc").save(output, format="JPEG")
        asset = MediaAsset.objects.create(
            title="Approved synthetic photo",
            alt_text="A synthetic solid-color test image",
            original=SimpleUploadedFile("photo.jpg", output.getvalue(), content_type="image/jpeg"),
            visibility="public",
            marketing_approved=True,
        )
        with pytest.raises(ValueError):
            _ = asset.original.url
        publish_asset(asset)
        assert set(asset.variants) == {"480", "800", "1200"}
        assert asset.status == "published"
        assert MediaAsset.objects.public().filter(pk=asset.pk).exists()
        paths = [Path(settings.MEDIA_ROOT) / name for name in asset.published_files]
        assert all(path.exists() for path in paths)
        unpublish_asset(asset)
        assert not any(path.exists() for path in paths)
        assert not MediaAsset.objects.public().filter(pk=asset.pk).exists()
    finally:
        original_field.storage = prior_storage
