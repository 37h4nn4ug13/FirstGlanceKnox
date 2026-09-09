import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from accounts import services, staff_services
from accounts.models import StaffInvitation, StaffProfile, User
from operations.models import AuditEvent, CleanerPayout, Notification

pytestmark = pytest.mark.django_db


def update_data(**overrides):
    return {
        "roles": ["Cleaner"],
        "display_name": "Taylor Test",
        "phone": "",
        "skills": "",
        "internal_notes": "",
        "default_commission_rate": "12.00",
        **overrides,
    }


def test_invite_reissue_and_activate_preserve_identity(team):
    invitation = services.invite_staff(
        actor=team["admin"], email="new@example.invalid", display_name="New employee", roles=["Salesperson", "Cleaner"]
    )
    old_token = services.invitation_token(invitation)
    renewed = staff_services.renew_invitation(actor=team["admin"], user=invitation.user)
    from django.core.signing import BadSignature

    with pytest.raises(BadSignature):
        services.invitation_from_token(old_token)
    services.accept_invitation(token=services.invitation_token(renewed), password="SyntheticValidPassword!2026")
    employee = User.objects.get(pk=invitation.user_id)
    assert employee.is_active and employee.staff_profile.is_active
    assert employee.has_role("Cleaner") and employee.has_role("Salesperson")
    assert not employee.is_staff and not employee.is_superuser
    assert AuditEvent.objects.filter(object_id=employee.public_id, action="staff.invited").exists()


def test_deactivation_revokes_old_sessions_and_preserves_pay_history(team, job, accepted_offer, lead):
    cleaner = team["cleaner"]
    old_client = Client()
    old_client.force_login(cleaner)
    assert old_client.get("/crew/").status_code == 200
    staff_services.deactivate_staff(actor=team["admin"], user=cleaner, reason="Employee departed")
    cleaner.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert not cleaner.is_active and not cleaner.has_usable_password()
    assert old_client.get("/crew/").status_code == 302
    assert accepted_offer.status == "withdrawn"
    assert accepted_offer.accepted_terms["fixed_amount"] == "85.00"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "reversed"
    invitation = staff_services.renew_invitation(actor=team["admin"], user=cleaner)
    services.accept_invitation(token=services.invitation_token(invitation), password="RehireDifferentPassword!2026")
    cleaner.refresh_from_db()
    assert cleaner.is_active and cleaner.staff_profile.is_active
    assert old_client.get("/crew/").status_code == 302


def test_deactivation_preserves_in_progress_work_and_alerts_admin(team, job, accepted_offer):
    from operations import services as domain

    domain.transition_job(actor=team["cleaner"], job=job, status="in_progress")
    staff_services.deactivate_staff(actor=team["admin"], user=team["cleaner"], reason="Access must end")
    job.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert job.status == "in_progress" and accepted_offer.status == "accepted"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "pending"
    assert Notification.objects.filter(recipient=team["admin"], kind="staff.handoff").exists()


def test_removing_sales_role_unassigns_open_leads_and_retains_commission(team, lead, invoice):
    from operations.models import CommissionEntry, Lead

    Lead.objects.filter(pk=lead.pk).update(status="follow_up")
    entry = CommissionEntry.objects.get(invoice=invoice)
    old_rate = entry.rate_snapshot
    staff_services.update_staff(actor=team["admin"], user=team["sales"], **update_data())
    lead.refresh_from_db()
    entry.refresh_from_db()
    assert lead.assigned_to is None
    assert entry.rate_snapshot == old_rate
    assert StaffProfile.objects.get(user=team["sales"]).default_commission_rate == 12


def test_self_lockout_and_owner_edits_rejected(team):
    with pytest.raises(ValidationError):
        staff_services.deactivate_staff(actor=team["admin"], user=team["admin"], reason="Mistake")
    with pytest.raises(ValidationError):
        staff_services.update_staff(actor=team["admin"], user=team["admin"], **update_data())
    owner = User.objects.create_superuser(email="owner@example.invalid", password="OwnerPassword2026!")
    StaffProfile.objects.create(user=owner, display_name="Owner")
    with pytest.raises(ValidationError):
        staff_services.deactivate_staff(actor=team["admin"], user=owner, reason="Mistake")
    with pytest.raises(PermissionDenied):
        staff_services.update_staff(actor=team["admin"], user=owner, **update_data(roles=["Admin"]))


@pytest.mark.parametrize("role", ["sales", "cleaner", "customer"])
def test_staff_management_endpoints_are_admin_only(client, team, role):
    client.force_login(team[role])
    for name in ["staff", "staff_invite", "staff_detail", "staff_deactivate", "staff_reinvite"]:
        kwargs = {"public_id": team["other_cleaner"].public_id} if name not in ["staff", "staff_invite"] else {}
        url = reverse("accounts:" + name, kwargs=kwargs)
        assert client.get(url).status_code == 403
        assert client.post(url, update_data()).status_code == 403


def test_staff_edit_view_and_invitation_failure_are_recoverable(client, team, settings, monkeypatch):
    client.force_login(team["admin"])
    url = reverse("accounts:staff_detail", args=[team["cleaner"].public_id])
    assert client.post(url, update_data(roles=["Cleaner", "Salesperson"])).status_code == 302
    employee = User.objects.get(pk=team["cleaner"].pk)
    assert employee.has_role("Salesperson")

    def fail(*args):
        raise OSError("Email provider offline")

    monkeypatch.setattr(services, "email_invitation", fail)
    response = client.post(
        reverse("accounts:staff_invite"),
        {"email": "invite@example.invalid", "display_name": "New", "roles": ["Cleaner"]},
        follow=True,
    )
    assert "email delivery failed" in response.content.decode()
    assert StaffInvitation.objects.filter(user__email="invite@example.invalid").count() == 1


def test_stale_admin_cannot_mutate_after_deactivation(team):
    another = team["other_sales"]
    another.groups.add(Group.objects.get(name="Admin"))
    staff_services.deactivate_staff(actor=team["admin"], user=another, reason="Access revoked")
    with pytest.raises(PermissionDenied):
        staff_services.update_staff(actor=another, user=team["cleaner"], **update_data())


@pytest.mark.parametrize("payload", [[], {"data": []}, "invalid"])
def test_malformed_offline_updates_return_review_message(client, team, payload):
    client.force_login(team["sales"])
    response = client.post(reverse("accounts:offline_sync"), payload, content_type="application/json")
    assert response.status_code == 409
    assert "error" in response.json()
