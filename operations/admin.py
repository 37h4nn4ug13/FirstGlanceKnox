from django.contrib import admin
from . import models


class ImmutableAdmin(admin.ModelAdmin):
    """Ledger changes go through the workspace service actions, even for superusers."""

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "email", "active", "do_not_contact"]
    search_fields = ["name", "email", "phone"]
    list_filter = ["kind", "active", "do_not_contact"]


@admin.register(models.Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["address_line1", "customer", "kind"]
    search_fields = ["address_line1", "customer__name"]


@admin.register(models.PriceBookItem)
class PriceBookAdmin(admin.ModelAdmin):
    list_display = ["name", "unit_price", "unit", "active", "requires_approval"]
    list_filter = ["active", "category"]


for model in [
    models.Estimate,
    models.EstimateLine,
    models.Job,
    models.JobOffer,
    models.Invoice,
    models.InvoiceLine,
    models.Payment,
    models.CommissionEntry,
    models.CleanerPayout,
    models.AuditEvent,
    models.AccessToken,
    models.OutboundMessage,
]:
    admin.site.register(model, ImmutableAdmin)
for model in [
    models.Contact,
    models.Lead,
    models.LeadVisit,
    models.AvailabilityBlock,
    models.RecurringPlan,
    models.Notification,
]:
    admin.site.register(model)
admin.site.site_header = "FirstGlanceKnox Administration"
admin.site.site_title = "FirstGlanceKnox"
admin.site.index_title = "Business configuration"
