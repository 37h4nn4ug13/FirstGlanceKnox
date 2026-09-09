from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.forms import formset_factory
from django.utils import timezone
from .models import Customer, Contact, Property, Lead, PriceBookItem, AvailabilityBlock, RecurringPlan


class QuickLeadForm(forms.Form):
    address = forms.CharField(label="Service address", max_length=240)
    name = forms.CharField(label="Customer or business name", max_length=180, required=False)
    kind = forms.ChoiceField(label="Property type", choices=Customer.Kind.choices)
    email = forms.EmailField(required=False)
    phone = forms.CharField(max_length=40, required=False)
    outcome = forms.ChoiceField(
        choices=[
            ("interested", "Interested"),
            ("no_answer", "No answer"),
            ("follow_up", "Follow up later"),
            ("estimate_requested", "Estimate requested"),
            ("not_interested", "Not interested"),
            ("do_not_contact", "Do not contact"),
        ]
    )
    message = forms.CharField(label="Visit notes", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    follow_up_at = forms.DateTimeField(
        label="Follow-up", required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    confirm_duplicate = forms.BooleanField(
        label="I reviewed the matching address and want to record a new visit.", required=False
    )


class LeadUpdateForm(forms.ModelForm):
    class Meta:
        model = Lead
        fields = ["status", "follow_up_at", "notes", "assigned_to"]
        widgets = {
            "follow_up_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not admin:
            self.fields.pop("assigned_to")
        else:
            self.fields["assigned_to"].queryset = (
                get_user_model().objects.filter(is_active=True, groups__name="Salesperson").distinct()
            )


class EstimateForm(forms.Form):
    discount = forms.DecimalField(label="Discount ($)", max_digits=12, decimal_places=2, min_value=0, initial=0)
    tax_rate = forms.DecimalField(
        label="Configured tax rate (%)",
        max_digits=6,
        decimal_places=3,
        min_value=0,
        max_value=100,
        initial=0,
        help_text="Use the business-approved rate for this service.",
    )
    expires_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    customer_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    terms = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))


class EstimateLineForm(forms.Form):
    price_book_item = forms.ModelChoiceField(
        label="Service", queryset=PriceBookItem.objects.filter(active=True), required=False
    )
    quantity = forms.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"), initial=1, required=False)
    description = forms.CharField(max_length=240, required=False, label="Description (optional override)")
    unit_price = forms.DecimalField(
        max_digits=12, decimal_places=2, min_value=0, required=False, label="Unit price ($, blank uses price book)"
    )
    unit = forms.CharField(max_length=40, required=False, label="Unit (blank uses price book)")

    def clean(self):
        data = super().clean()
        if (data.get("price_book_item") or data.get("description")) and not data.get("quantity"):
            self.add_error("quantity", "Enter a quantity for this service.")
        if data.get("description") and not data.get("price_book_item") and data.get("unit_price") is None:
            self.add_error("unit_price", "Enter the price for a custom service.")
        return data


EstimateLineFormSet = formset_factory(EstimateLineForm, extra=5, max_num=20, validate_max=True, can_delete=True)


class EstimateRevisionForm(EstimateForm):
    revision_reason = forms.CharField(
        max_length=2000, widget=forms.Textarea(attrs={"rows": 2}), label="Reason for revision"
    )


class ScheduleForm(forms.Form):
    scheduled_start = forms.DateTimeField(
        label="Start (Knoxville time)", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    scheduled_end = forms.DateTimeField(
        label="Finish (Knoxville time)", widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )

    def clean(self):
        data = super().clean()
        start, end = data.get("scheduled_start"), data.get("scheduled_end")
        if start and end and end <= start:
            raise forms.ValidationError("Finish must be after the start time.")
        if start and start < timezone.now():
            self.add_error("scheduled_start", "Choose a future appointment.")
        return data


class OfferForm(forms.Form):
    cleaner = forms.ModelChoiceField(
        queryset=get_user_model().objects.filter(is_active=True, groups__name="Cleaner").distinct()
    )
    fixed_amount = forms.DecimalField(label="Agreed fixed pay ($)", min_value=0, decimal_places=2, max_digits=12)
    expires_at = forms.DateTimeField(required=False, widget=forms.DateTimeInput(attrs={"type": "datetime-local"}))
    crew_slot = forms.IntegerField(initial=1, min_value=1)


class RescheduleForm(ScheduleForm):
    reason = forms.CharField(
        label="Reason for the schedule change", max_length=2000, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("scheduled_start", "scheduled_end"):
            self.fields[name].widget.format = "%Y-%m-%dT%H:%M"


class ChangeReasonForm(forms.Form):
    reason = forms.CharField(label="Reason", max_length=2000, widget=forms.Textarea(attrs={"rows": 3}))


class InvoiceForm(forms.Form):
    due_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    purchase_order = forms.CharField(label="Purchase order", required=False, max_length=100)


class PaymentForm(forms.Form):
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = forms.ChoiceField(
        choices=[
            ("cash", "Cash"),
            ("check", "Check"),
            ("bank_transfer", "Bank transfer"),
            ("card_external", "External card payment"),
            ("other", "Other"),
        ]
    )
    reference = forms.CharField(max_length=160, required=False)
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    idempotency_key = forms.UUIDField(widget=forms.HiddenInput)


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "name",
            "kind",
            "email",
            "phone",
            "payment_terms_days",
            "do_not_contact",
            "marketing_consent",
            "internal_notes",
        ]
        widgets = {"internal_notes": forms.Textarea(attrs={"rows": 3})}


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            "name",
            "kind",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "stories",
            "approximate_windows",
            "access_instructions",
            "hazards",
            "customer_notes",
        ]
        widgets = {
            name: forms.Textarea(attrs={"rows": 2}) for name in ["access_instructions", "hazards", "customer_notes"]
        }


class ContactForm(forms.ModelForm):
    class Meta:
        model = Contact
        fields = ["name", "title", "email", "phone", "preferred_channel", "is_primary", "is_billing", "is_site"]


class PriceBookForm(forms.ModelForm):
    class Meta:
        model = PriceBookItem
        fields = [
            "name",
            "description",
            "unit",
            "unit_price",
            "category",
            "active",
            "requires_approval",
            "commissionable",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = AvailabilityBlock
        fields = ["staff", "starts_at", "ends_at", "reason"]
        widgets = {
            name: forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})
            for name in ["starts_at", "ends_at"]
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["staff"].queryset = (
            get_user_model()
            .objects.filter(is_active=True, groups__name__in=["Admin", "Salesperson", "Cleaner"])
            .distinct()
        )


class RecurringForm(forms.ModelForm):
    class Meta:
        model = RecurringPlan
        fields = ["name", "interval_days", "duration_minutes", "next_visit_at", "purchase_order"]
        widgets = {"next_visit_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}


class RecurringEditForm(RecurringForm):
    class Meta(RecurringForm.Meta):
        fields = RecurringForm.Meta.fields + ["active"]
        widgets = {"next_visit_at": forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"})}
