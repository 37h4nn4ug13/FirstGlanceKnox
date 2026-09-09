from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from .models import MediaAsset, GalleryCollection, BeforeAfterPair, Service, ServiceArea, Testimonial, FeaturedProject
from .media import publish_asset, unpublish_asset


@admin.register(MediaAsset)
class MediaAssetAdmin(admin.ModelAdmin):
    list_display = ('title', 'kind', 'category', 'visibility', 'marketing_approved', 'status')
    list_filter = ('status', 'visibility', 'marketing_approved', 'category', 'kind')
    search_fields = ('title', 'caption')
    readonly_fields = ('status', 'public_url', 'poster_url', 'variants', 'published_files', 'width', 'height', 'file_size', 'mime_type')
    actions = ('publish_approved', 'unpublish')

    @admin.action(description='Publish approved media and generate responsive files')
    def publish_approved(self, request, queryset):
        for asset in queryset:
            try:
                publish_asset(asset)
            except ValidationError as exc:
                self.message_user(request, f'{asset.title}: {exc}', level=messages.ERROR)
            else:
                self.message_user(request, f'Published {asset.title}.')

    @admin.action(description='Unpublish selected media')
    def unpublish(self, request, queryset):
        for asset in queryset:
            unpublish_asset(asset)


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ('title', 'category', 'published', 'display_order')


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ('name', 'verified', 'permission_to_publish', 'published')


admin.site.register([ServiceArea, GalleryCollection, BeforeAfterPair, FeaturedProject])
