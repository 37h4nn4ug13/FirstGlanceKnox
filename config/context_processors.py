from django.conf import settings


def business(request):
    return {
        "business_name": settings.BUSINESS_NAME,
        "business_phone": settings.BUSINESS_PHONE,
        "business_email": settings.BUSINESS_EMAIL,
        "local_preview": settings.DEBUG,
        "site_url": settings.SITE_URL,
    }
