from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .forms import AccountChangeForm, AccountCreationForm
from .models import NotificationPreference, PushSubscription, StaffInvitation, StaffProfile, User


@admin.register(User)
class AccountAdmin(UserAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    ordering = ("email",)
    list_display = ("email", "first_name", "last_name", "is_active", "is_staff")
    search_fields = ("email", "first_name", "last_name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("first_name", "last_name")}),
        ("Access", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2", "is_staff", "is_active")}),
    )


admin.site.register(StaffProfile)
admin.site.register(NotificationPreference)
admin.site.register(PushSubscription)
admin.site.register(StaffInvitation)
