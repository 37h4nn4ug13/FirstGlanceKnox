import hashlib
import json

from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from django.utils.crypto import get_random_string

from .content import HOUSE, INTERIOR, COMMERCIAL, WINDOW, SERVICES, FAQS
from .forms import QuoteForm
from .models import Service, MediaAsset, BeforeAfterPair, Testimonial, ServiceArea


def context(request, **extra):
    public_services = list(Service.objects.filter(published=True))
    domain = getattr(settings, 'SITE_URL', '')
    return {'house_image': HOUSE, 'interior_image': INTERIOR, 'commercial_image': COMMERCIAL,
            'window_image': WINDOW, 'services': public_services or SERVICES, 'faqs': FAQS,
            'canonical_url': (domain.rstrip('/') + request.path) if domain else '',
            'meta_description': 'A clearer view for your home or business. Request a window-cleaning quote from FirstGlanceKnox in the Knoxville area.',
            'business_schema': json.dumps({'@context': 'https://schema.org', '@type': 'LocalBusiness', 'name': 'FirstGlanceKnox', 'description': 'Knoxville-area window cleaning for residential and commercial properties.', 'areaServed': {'@type': 'City', 'name': 'Knoxville'}}), **extra}


def home(request):
    return render(request, 'marketing/home.html', context(request, testimonials=Testimonial.objects.filter(published=True, verified=True, permission_to_publish=True)[:3], featured_media=MediaAsset.objects.public()[:4], areas=ServiceArea.objects.filter(confirmed=True)))


def audience(request, kind):
    if kind not in ('residential', 'commercial'):
        raise Http404
    return render(request, 'marketing/audience.html', context(request, kind=kind))


def service(request, slug):
    selected = Service.objects.filter(published=True, slug=slug).first()
    if selected is None:
        selected = next((item for item in SERVICES if item['slug'] == slug), None)
    if selected is None:
        raise Http404
    return render(request, 'marketing/service.html', context(request, service=selected))


def gallery(request):
    category = request.GET.get('category', '')
    if category not in ('residential', 'commercial'):
        category = ''
    assets = MediaAsset.objects.public()
    if category:
        assets = assets.filter(category=category)
    public_ids = MediaAsset.objects.public().values('pk')
    pairs = BeforeAfterPair.objects.filter(published=True, before_id__in=public_ids, after_id__in=public_ids).select_related('before', 'after')
    mode = 'before-after' if request.GET.get('mode') == 'before-after' else 'all'
    return render(request, 'marketing/gallery.html', context(request, assets=assets, pairs=pairs, category=category, mode=mode))


@require_http_methods(['GET', 'POST'])
def quote(request):
    initial_kind = request.GET.get('type', 'residential')
    initial_kind = initial_kind if initial_kind in ('residential', 'commercial') else 'residential'
    form = QuoteForm(request.POST or None, initial={'kind': initial_kind})
    if request.method == 'POST':
        if form.is_valid():
            if form.cleaned_data['website']:
                return redirect('marketing:quote_success')
            identity = hashlib.sha256(request.META.get('REMOTE_ADDR', '').encode()).hexdigest()
            key = f'quote-limit:{identity}'
            cache.add(key, 0, timeout=3600)
            try:
                count = cache.incr(key)
            except ValueError:
                cache.set(key, 1, timeout=3600)
                count = 1
            if count > 8:
                form.add_error(None, 'You have sent several requests. Please try again later.')
                return render(request, 'marketing/quote.html', context(request, form=form), status=429)
            from operations.services import capture_lead
            values = {name: form.cleaned_data[name] for name in ('name', 'email', 'phone', 'address', 'kind', 'services', 'message', 'preferred_date')}
            try:
                capture_lead(**values, source='website', idempotency_key=request.session.get('quote_submission_key'))
            except ValidationError:
                form.add_error(None, 'We could not process this request. Please check your details or contact the business directly.')
            else:
                request.session.pop('quote_submission_key', None)
                return redirect('marketing:quote_success')
        return render(request, 'marketing/quote.html', context(request, form=form), status=400)
    if not request.session.get('quote_submission_key'):
        request.session['quote_submission_key'] = get_random_string(40)
    return render(request, 'marketing/quote.html', context(request, form=form))


def quote_success(request):
    return render(request, 'marketing/quote_success.html', context(request))


def page(request, slug):
    pages = {'about': 'About FirstGlanceKnox', 'areas': 'A clearer view, close to home.', 'contact': 'Let’s talk windows.', 'faq': 'A few things you might be wondering.', 'privacy': 'Privacy policy', 'terms': 'Terms of service'}
    if slug not in pages:
        raise Http404
    return render(request, 'marketing/page.html', context(request, page=slug, page_title=pages[slug], areas=ServiceArea.objects.filter(confirmed=True)))


def robots(request):
    body = 'User-agent: *\nAllow: /\nDisallow: /crew/\nDisallow: /portal/\nDisallow: /admin/\nDisallow: /accounts/\n'
    domain = getattr(settings, 'SITE_URL', '')
    if domain:
        body += f'Sitemap: {domain.rstrip("/")}/sitemap.xml\n'
    return HttpResponse(body, content_type='text/plain')


def sitemap(request):
    from xml.sax.saxutils import escape
    domain = getattr(settings, 'SITE_URL', '').rstrip('/') or request.build_absolute_uri('/').rstrip('/')
    urls = ['home', 'residential', 'commercial', 'gallery', 'about', 'areas', 'quote', 'contact', 'faq']
    entries = ''.join(f'<url><loc>{escape(domain + reverse("marketing:" + name))}</loc></url>' for name in urls)
    return HttpResponse('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + entries + '</urlset>', content_type='application/xml')


def not_found(request, exception):
    return render(request, 'marketing/404.html', status=404)


def server_error(request):
    return render(request, 'marketing/500.html', status=500)
