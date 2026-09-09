from django import forms


class EstimateResponseForm(forms.Form):
    signature = forms.CharField(
        max_length=180,
        label="Your full name",
        help_text="Type your name to record your approval.",
        widget=forms.TextInput(attrs={"autocomplete": "name"}),
    )
    agreement = forms.BooleanField(label="I approve this scope of work, price, and terms.")


class EstimateDeclineForm(forms.Form):
    reason = forms.CharField(
        max_length=2000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Anything you'd like us to know? (optional)",
    )


class RepeatServiceForm(forms.Form):
    property = forms.ModelChoiceField(queryset=None, label="Service location")
    notes = forms.CharField(
        max_length=3000,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="What would you like cleaned?",
        help_text="Include your preferred timing. We'll confirm scope and availability.",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        from operations.models import Property

        self.fields["property"].queryset = Property.objects.filter(customer__user=user, customer__active=True)
