"""Private originals; only validated, explicitly approved derivatives are public."""
from io import BytesIO
from pathlib import Path
import uuid

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageOps, UnidentifiedImageError


def validate_upload(upload, kind='image'):
    max_size = 20 * 1024 * 1024 if kind == 'image' else 100 * 1024 * 1024
    if upload.size > max_size:
        raise ValidationError(f'Upload must be smaller than {max_size // (1024 * 1024)} MB.')
    extension = Path(upload.name).suffix.lower()
    try:
        upload.open('rb')
        upload.seek(0)
        if kind == 'image':
            if extension not in {'.jpg', '.jpeg', '.png', '.webp'}:
                raise ValidationError('Use a JPEG, PNG, or WebP image.')
            with Image.open(upload) as picture:
                if picture.format not in {'JPEG', 'PNG', 'WEBP'} or picture.width * picture.height > 40_000_000:
                    raise ValidationError('Unsupported image or more than 40 megapixels.')
                picture.verify()
        else:
            header = upload.read(16)
            if not ((extension == '.mp4' and header[4:8] == b'ftyp') or (extension == '.webm' and header[:4] == b'\x1aE\xdf\xa3')):
                raise ValidationError('Use a valid MP4 or WebM video.')
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError('This image could not be read safely.') from exc
    finally:
        upload.seek(0)


def publish_asset(asset):
    """Explicit admin operation, never called on private job evidence automatically."""
    if not asset.marketing_approved or asset.visibility != 'public':
        raise ValidationError('Marketing consent and public visibility are required.')
    asset.status = 'published'
    asset.full_clean()
    if not asset.original:
        raise ValidationError('Upload an original before publishing.')
    validate_upload(asset.original, asset.kind)
    asset.file_size = asset.original.size
    old_files = asset.published_files[:]
    new_files = []
    if asset.kind == 'image':
        asset.original.open('rb')
        with Image.open(asset.original) as original:
            picture = ImageOps.exif_transpose(original).convert('RGB')
            asset.width, asset.height = picture.size
            variants = {}
            for width in (480, 800, 1200, 1800):
                if width > picture.width and variants:
                    break
                variant = picture.copy()
                variant.thumbnail((width, width * 6))
                output = BytesIO()
                variant.save(output, format='WEBP', quality=84, method=4)
                path = default_storage.save(f'marketing/published/{uuid.uuid4().hex}.webp', ContentFile(output.getvalue()))
                new_files.append(path)
                variants[str(variant.width)] = default_storage.url(path)
            asset.variants = variants
            asset.public_url = list(variants.values())[-1]
            asset.mime_type = 'image/webp'
    else:
        asset.original.open('rb')
        path = default_storage.save(f'marketing/published/{uuid.uuid4().hex}{Path(asset.original.name).suffix}', asset.original)
        new_files.append(path)
        asset.public_url = default_storage.url(path)
        asset.mime_type = 'video/mp4' if path.endswith('.mp4') else 'video/webm'
        asset.poster.open('rb')
        with Image.open(asset.poster) as original:
            picture = ImageOps.exif_transpose(original).convert('RGB')
            picture.thumbnail((1200, 1200))
            output = BytesIO()
            picture.save(output, format='WEBP', quality=84)
            poster_path = default_storage.save(f'marketing/published/{uuid.uuid4().hex}.webp', ContentFile(output.getvalue()))
            new_files.append(poster_path)
            asset.poster_url = default_storage.url(poster_path)
    asset.published_files = new_files
    asset.save()
    for name in old_files:
        default_storage.delete(name)
    return asset


def unpublish_asset(asset):
    names = asset.published_files[:]
    asset.status = 'draft'
    asset.public_url = ''
    asset.poster_url = ''
    asset.variants = {}
    asset.published_files = []
    asset.save(update_fields=['status', 'public_url', 'poster_url', 'variants', 'published_files'])
    for name in names:
        default_storage.delete(name)
