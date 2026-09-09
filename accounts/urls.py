from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views
from . import offline
from . import staff_views

app_name = "accounts"
urlpatterns = [
    path("staff/", staff_views.staff_list, name="staff"),
    path("staff/invite/", staff_views.staff_invite, name="staff_invite"),
    path("staff/<uuid:public_id>/", staff_views.staff_detail, name="staff_detail"),
    path("staff/<uuid:public_id>/deactivate/", staff_views.staff_deactivate, name="staff_deactivate"),
    path("staff/<uuid:public_id>/invite/", staff_views.staff_reinvite, name="staff_reinvite"),
    path("api/offline/", offline.sync, name="offline_sync"),
    path("api/summary/", offline.summary, name="offline_summary"),
    path("login/", views.AccountLoginView.as_view(), name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile, name="profile"),
    path("invite/", staff_views.staff_invite, name="invite"),
    path("invite/<uuid:public_id>/revoke/", staff_views.invitation_revoke, name="revoke_invitation"),
    path("accept-invitation/<str:token>/", views.invitation_accept, name="accept_invitation"),
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="accounts/password_reset.html",
            email_template_name="accounts/password_reset_email.txt",
            subject_template_name="accounts/password_reset_subject.txt",
            success_url=reverse_lazy("accounts:password_reset_done"),
        ),
        name="password_reset",
    ),
    path(
        "password-reset/sent/",
        auth_views.PasswordResetDoneView.as_view(template_name="accounts/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="accounts/password_reset_confirm.html",
            success_url=reverse_lazy("accounts:password_reset_complete"),
        ),
        name="password_reset_confirm",
    ),
    path(
        "reset/complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="accounts/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("api/session/", views.session_info, name="session_info"),
    path("api/push/", views.subscribe_push, name="subscribe_push"),
    path("push/<int:subscription_id>/disable/", views.unsubscribe_push, name="unsubscribe_push"),
]
