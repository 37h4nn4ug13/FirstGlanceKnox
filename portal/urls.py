from django.urls import path

from . import views
from .evidence import evidence_view

app_name = "portal"
urlpatterns = [
    path("evidence/<uuid:pk>/", evidence_view, name="evidence"),
    path("", views.home, name="home"),
    path("request-service/", views.repeat_service, name="repeat_service"),
    path("estimate/<str:token>/", views.estimate, name="estimate"),
    path("estimate/<str:token>/pdf/", views.pdf, {"kind": "estimate"}, name="estimate_pdf"),
    path("invoice/<str:token>/", views.invoice, name="invoice"),
    path("invoice/<str:token>/pdf/", views.pdf, {"kind": "invoice"}, name="invoice_pdf"),
    path("estimates/<uuid:pk>/", views.estimate, name="estimate_account"),
    path("estimates/<uuid:pk>/pdf/", views.pdf, {"kind": "estimate"}, name="estimate_account_pdf"),
    path("invoices/<uuid:pk>/", views.invoice, name="invoice_account"),
    path("invoices/<uuid:pk>/pdf/", views.pdf, {"kind": "invoice"}, name="invoice_account_pdf"),
]
