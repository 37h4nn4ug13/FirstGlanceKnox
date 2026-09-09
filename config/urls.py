from django.contrib import admin
from django.urls import include, path
from accounts import views as account_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("portal/", include("portal.urls")),
    path("crew/manifest.webmanifest", account_views.crew_manifest),
    path("crew/sw.js", account_views.crew_service_worker),
    path("crew/", include("operations.urls")),
    path("", include("marketing.urls")),
]

handler404 = "config.views.not_found"
handler500 = "config.views.server_error"
