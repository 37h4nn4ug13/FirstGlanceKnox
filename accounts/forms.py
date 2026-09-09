from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm

from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Email address", widget=forms.EmailInput(attrs={"autocomplete": "username", "autofocus": True})
    )

    def clean_username(self):
        return self.cleaned_data["username"].lower()


class AccountCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class AccountChangeForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("first_name", "last_name")


class NotificationPreferenceForm(forms.Form):
    email_enabled = forms.BooleanField(required=False, label="Email notifications")


class InvitationForm(forms.Form):
    email = forms.EmailField()
    display_name = forms.CharField(max_length=120)
    roles = forms.MultipleChoiceField(
        choices=[("Salesperson", "Salesperson"), ("Cleaner", "Cleaner"), ("Admin", "Admin")],
        widget=forms.CheckboxSelectMultiple,
    )


class StaffEditForm(forms.Form):
    display_name = forms.CharField(max_length=120)
    phone = forms.CharField(max_length=30, required=False)
    roles = forms.MultipleChoiceField(
        choices=InvitationForm.base_fields["roles"].choices, widget=forms.CheckboxSelectMultiple
    )
    default_commission_rate = forms.DecimalField(
        label="Default commission (%) for future agreements", min_value=0, max_value=100, max_digits=5, decimal_places=2
    )
    skills = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))
    internal_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
