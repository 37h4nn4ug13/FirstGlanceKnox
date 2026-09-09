import uuid
import builtins
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateMediaStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=getattr(settings, 'PRIVATE_MEDIA_ROOT', Path(settings.BASE_DIR) / 'private_media'))

    def url(self, name):
        raise ValueError('Original marketing uploads are private. Use an approved derivative.')


def original_upload_path(instance, filename):
    return f'marketing/originals/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'


class Service(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    summary = models.CharField(max_length=250)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=[('residential', 'Residential'), ('commercial', 'Commercial'), ('both', 'Both')], default='both')
    display_order = models.PositiveIntegerField(default=0)
    published = models.BooleanField(default=False)
    meta_description = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ['display_order', 'title']

    def __str__(self):
        return self.title


class ServiceArea(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    confirmed = models.BooleanField(default=False, help_text='Only confirmed coverage appears publicly.')
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name


class PublicMediaQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status='published', visibility='public', marketing_approved=True).exclude(public_url='')


class MediaAsset(models.Model):
    class Kind(models.TextChoices):
        IMAGE = 'image', 'Image'
        VIDEO = 'video', 'Video'

    title = models.CharField(max_length=150)
    caption = models.TextField(blank=True)
    alt_text = models.CharField(max_length=250, blank=True)
    decorative = models.BooleanField(default=False)
    kind = models.CharField(max_length=8, choices=Kind.choices, default=Kind.IMAGE)
    original = models.FileField(storage=PrivateMediaStorage(), upload_to=original_upload_path, blank=True)
    public_url = models.CharField(max_length=500, blank=True, editable=False)
    variants = models.JSONField(default=dict, blank=True, editable=False)
    poster = models.ImageField(storage=PrivateMediaStorage(), upload_to=original_upload_path, blank=True)
    poster_url = models.CharField(max_length=500, blank=True, editable=False)
    published_files = models.JSONField(default=list, blank=True, editable=False)
    transcript = models.TextField(blank=True, help_text='Required for meaningful spoken video content.')
    category = models.CharField(max_length=20, choices=[('residential', 'Residential'), ('commercial', 'Commercial')], default='residential')
    status = models.CharField(max_length=12, choices=[('draft', 'Draft'), ('published', 'Published')], default='draft')
    visibility = models.CharField(max_length=12, choices=[('internal', 'Internal only'), ('customer', 'Customer visible'), ('public', 'Public marketing')], default='internal')
    marketing_approved = models.BooleanField(default=False, help_text='Confirm owner/customer permission before publishing.')
    consent_note = models.TextField(blank=True)
    captured_at = models.DateField(null=True, blank=True)
    location_label = models.CharField(max_length=100, blank=True, help_text='Neighborhood/city only; do not expose a private address.')
    width = models.PositiveIntegerField(null=True, blank=True, editable=False)
    height = models.PositiveIntegerField(null=True, blank=True, editable=False)
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    file_size = models.PositiveBigIntegerField(null=True, blank=True, editable=False)
    mime_type = models.CharField(max_length=80, blank=True, editable=False)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey('operations.Customer', null=True, blank=True, on_delete=models.SET_NULL)
    property = models.ForeignKey('operations.Property', null=True, blank=True, on_delete=models.SET_NULL)
    job = models.ForeignKey('operations.Job', null=True, blank=True, on_delete=models.SET_NULL)
    objects = PublicMediaQuerySet.as_manager()

    class Meta:
        ordering = ['display_order', '-created_at']
        constraints = [models.CheckConstraint(condition=~models.Q(status='published') | models.Q(marketing_approved=True, visibility='public'), name='published_media_requires_consent')]

    def clean(self):
        if self.status == 'published' and (not self.marketing_approved or self.visibility != 'public'):
            raise ValidationError('Publishing requires marketing consent and public visibility.')
        if self.status == 'published' and not self.decorative and not self.alt_text:
            raise ValidationError({'alt_text': 'Write descriptive alternative text before publishing.'})
        if self.kind == 'video' and self.status == 'published' and not self.poster:
            raise ValidationError({'poster': 'A video poster is required for publication.'})
        if self.original:
            from .media import validate_upload
            validate_upload(self.original, self.kind)
        if self.poster:
            from .media import validate_upload
            validate_upload(self.poster, 'image')

    @builtins.property
    def srcset(self):
        if self.published_files and self.kind == 'image':
            from django.core.files.storage import default_storage
            return ', '.join(f'{default_storage.url(path)} {width}w' for width, path in zip(sorted(self.variants, key=int), self.published_files))
        return ', '.join(f'{url} {width}w' for width, url in self.variants.items())

    @builtins.property
    def source_url(self):
        # Resolve at render time so object-storage signed URLs do not expire in the database.
        if self.published_files:
            from django.core.files.storage import default_storage
            return default_storage.url(self.published_files[-1 if self.kind == 'image' else 0])
        return self.public_url

    @builtins.property
    def poster_source_url(self):
        if self.kind == 'video' and len(self.published_files) > 1:
            from django.core.files.storage import default_storage
            return default_storage.url(self.published_files[-1])
        return self.poster_url

    def __str__(self):
        return self.title


class GalleryCollection(models.Model):
    title = models.CharField(max_length=120)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    assets = models.ManyToManyField(MediaAsset, blank=True)
    published = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class BeforeAfterPair(models.Model):
    title = models.CharField(max_length=150)
    before = models.ForeignKey(MediaAsset, on_delete=models.PROTECT, related_name='before_pairs')
    after = models.ForeignKey(MediaAsset, on_delete=models.PROTECT, related_name='after_pairs')
    published = models.BooleanField(default=False)

    def clean(self):
        if self.published and self.before_id and self.after_id:
            public_ids = MediaAsset.objects.public().filter(pk__in=[self.before_id, self.after_id]).values_list('pk', flat=True)
            if set(public_ids) != {self.before_id, self.after_id}:
                raise ValidationError('Both images must be approved and published before this pair is published.')
        if self.before_id == self.after_id:
            raise ValidationError('Choose two different images.')

    def __str__(self):
        return self.title


class FeaturedProject(models.Model):
    title = models.CharField(max_length=150)
    summary = models.TextField()
    media = models.ForeignKey(MediaAsset, on_delete=models.PROTECT)
    service = models.ForeignKey(Service, null=True, blank=True, on_delete=models.SET_NULL)
    published = models.BooleanField(default=False)

    def __str__(self):
        return self.title


class Testimonial(models.Model):
    name = models.CharField(max_length=100)
    quote = models.TextField()
    source_label = models.CharField(max_length=100, blank=True)
    verified = models.BooleanField(default=False)
    permission_to_publish = models.BooleanField(default=False)
    published = models.BooleanField(default=False)

    def __str__(self):
        return self.name
