import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower

from .managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        constraints = [models.UniqueConstraint(Lower("email"), name="accounts_email_ci_unique")]

    def has_role(self, *roles):
        from operations.services import has_role

        return has_role(self, *roles)

    def __str__(self):
        return self.get_full_name() or self.email


class StaffProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_profile")
    display_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30, blank=True)
    is_active = models.BooleanField(default=True)
    skills = models.TextField(blank=True)
    onboarding_state = models.CharField(
        max_length=20,
        choices=[("invited", "Invited"), ("active", "Active"), ("inactive", "Inactive")],
        default="active",
    )
    default_commission_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    internal_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(default_commission_rate__gte=0, default_commission_rate__lte=100),
                name="staff_commission_between_0_100",
            )
        ]

    def __str__(self):
        return self.display_name or str(self.user)


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=False)


class PushSubscription(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=2048, unique=True)
    p256dh = models.CharField(max_length=256)
    auth = models.CharField(max_length=256)
    device_name = models.CharField(max_length=120, default="This browser")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)


class StaffInvitation(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="invitations")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sent_invitations")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class OfflineReceipt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    client_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    result = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "client_id"], name="offline_user_client_unique")]
