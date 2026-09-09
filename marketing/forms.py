from django import forms
from django.utils import timezone


class QuoteForm(forms.Form):
    name = forms.CharField(max_length=120, label='Full name', widget=forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'Your name'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'autocomplete': 'email', 'placeholder': 'you@example.com'}))
    phone = forms.CharField(max_length=30, widget=forms.TextInput(attrs={'autocomplete': 'tel', 'type': 'tel', 'placeholder': '(865) 000-0000'}))
    address = forms.CharField(max_length=300, label='Property address', widget=forms.TextInput(attrs={'autocomplete': 'street-address', 'placeholder': 'Street, city, and ZIP code'}))
    kind = forms.ChoiceField(label='Property type', choices=[('residential', 'Residential'), ('commercial', 'Commercial')], widget=forms.RadioSelect)
    services = forms.MultipleChoiceField(required=False, label='What can we help with?', choices=[('interior', 'Interior windows'), ('exterior', 'Exterior windows'), ('screens', 'Screens & tracks'), ('storefront', 'Storefront or commercial'), ('other', 'Not sure yet')], widget=forms.CheckboxSelectMultiple)
    preferred_date = forms.DateField(required=False, label='Preferred service date', widget=forms.DateInput(attrs={'type': 'date'}), help_text='Optional. We will confirm availability with you.')
    message = forms.CharField(max_length=3000, required=False, label='Tell us a little about your property', widget=forms.Textarea(attrs={'rows': 4, 'placeholder': 'Number of windows, access details, or anything you would like us to know…'}))
    consent = forms.BooleanField(label='I agree to be contacted about this quote request.')
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}))

    def clean_preferred_date(self):
        value = self.cleaned_data.get('preferred_date')
        if value and value < timezone.localdate():
            raise forms.ValidationError('Choose today or a future date.')
        return value
