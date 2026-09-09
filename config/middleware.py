import hashlib
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.cache import patch_cache_control


class RequestSafetyMiddleware:
    """Shared fixed-window throttle. Reverse proxies must enforce body/connection limits too."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        protected = request.path.startswith(("/accounts/", "/portal/", "/quote/"))
        if protected and request.method == "POST":
            digest = hashlib.sha256(request.META.get("REMOTE_ADDR", "unknown").encode()).hexdigest()
            key = f"throttle:{request.path.split('/')[1]}:{digest}"
            if cache.add(key, 1, 600):
                count = 1
            else:
                try:
                    count = cache.incr(key)
                except ValueError:
                    cache.set(key, 1, 600)
                    count = 1
            if count > 30:
                response = HttpResponse("Too many attempts. Please try again in 10 minutes.", status=429)
                response["Retry-After"] = "600"
                return response
        response = self.get_response(request)
        if request.path.startswith(("/crew/", "/portal/", "/accounts/", "/admin/")):
            patch_cache_control(response, private=True, no_store=True)
        response["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=(self)"
        return response
