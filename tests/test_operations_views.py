from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from operations.models import AuditEvent, CleanerPayout, Notification

pytestmark = pytest.mark.django_db


def reschedule_data(job):
    start = timezone.localtime(job.scheduled_start + timedelta(days=1))
    return {
        "scheduled_start": start.strftime("%Y-%m-%dT%H:%M"),
        "scheduled_end": (start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"),
        "reason": "Customer requested a new appointment",
    }


def test_admin_reschedules_with_fresh_acceptance_required(client, team, job, accepted_offer):
    client.force_login(team["admin"])
    response = client.post(reverse("operations:job_reschedule", args=[job.pk]), reschedule_data(job))
    assert response.status_code == 302
    job.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert job.status == "scheduled"
    assert accepted_offer.status == "superseded"
    assert accepted_offer.accepted_terms["fixed_amount"] == "85.00"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "reversed"
    assert AuditEvent.objects.filter(action="job.rescheduled", object_id=job.pk).exists()
    note = Notification.objects.get(recipient=team["cleaner"], kind="offer.superseded")
    client.force_login(team["cleaner"])
    assert client.get(note.link).status_code == 200


def test_unchanged_schedule_preserves_accepted_pay(client, team, job, accepted_offer):
    client.force_login(team["admin"])
    response = client.post(
        reverse("operations:job_reschedule", args=[job.pk]),
        {
            "scheduled_start": timezone.localtime(job.scheduled_start).isoformat(),
            "scheduled_end": timezone.localtime(job.scheduled_end).isoformat(),
            "reason": "Accidentally submitted the original time",
        },
    )
    assert response.status_code == 200
    assert "different appointment time" in response.content.decode()
    accepted_offer.refresh_from_db()
    assert accepted_offer.status == "accepted"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "pending"


def test_conflict_preserves_original_appointment_and_offer(client, team, job, accepted_offer):
    from operations.models import AvailabilityBlock

    start = job.scheduled_start + timedelta(days=1)
    AvailabilityBlock.objects.create(starts_at=start - timedelta(minutes=1), ends_at=start + timedelta(hours=3))
    original = job.scheduled_start
    client.force_login(team["admin"])
    response = client.post(reverse("operations:job_reschedule", args=[job.pk]), reschedule_data(job))
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    job.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert job.scheduled_start == original
    assert accepted_offer.status == "accepted"


@pytest.mark.parametrize("role", ["sales", "cleaner", "customer"])
@pytest.mark.parametrize("action", ["job_reschedule", "job_cancel", "offer_withdraw"])
def test_job_management_is_admin_only(client, team, job, accepted_offer, role, action):
    client.force_login(team[role])
    pk = accepted_offer.pk if action == "offer_withdraw" else job.pk
    url = reverse("operations:" + action, args=[pk])
    assert client.get(url).status_code == 403
    assert client.post(url, {**reschedule_data(job), "reason": "Unauthorized change"}).status_code == 403
    job.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert job.status == "confirmed"
    assert accepted_offer.status == "accepted"


@pytest.mark.parametrize("action", ["job_cancel", "offer_withdraw"])
def test_reason_required_and_get_never_mutates(client, team, job, accepted_offer, action):
    client.force_login(team["admin"])
    pk = accepted_offer.pk if action == "offer_withdraw" else job.pk
    url = reverse("operations:" + action, args=[pk])
    assert client.get(url).status_code == 200
    response = client.post(url, {"reason": "   "})
    assert response.status_code == 200
    assert response.context["form"].errors["reason"]
    accepted_offer.refresh_from_db()
    assert accepted_offer.status == "accepted"


def test_cancel_retains_history_and_releases_pending_pay(client, team, job, accepted_offer):
    client.force_login(team["admin"])
    url = reverse("operations:job_cancel", args=[job.pk])
    assert client.post(url, {"reason": "Customer canceled"}).status_code == 302
    job.refresh_from_db()
    accepted_offer.refresh_from_db()
    assert job.status == "canceled"
    assert job.cancellation_reason == "Customer canceled"
    assert accepted_offer.status == "withdrawn"
    payout = CleanerPayout.objects.get(offer=accepted_offer)
    assert payout.status == "reversed" and payout.amount == Decimal("85.00")
    page = client.get(reverse("operations:job_detail", args=[job.pk])).content.decode()
    assert "Customer canceled" in page
    assert "Reschedule appointment" not in page and "＋ Offer job" not in page
    assert client.post(url, {"reason": "Repeated request"}).status_code == 200
    assert AuditEvent.objects.filter(action="job.canceled", object_id=job.pk).count() == 1


def test_withdraw_releases_slot_but_keeps_customer_appointment(client, team, job, accepted_offer):
    client.force_login(team["admin"])
    response = client.post(
        reverse("operations:offer_withdraw", args=[accepted_offer.pk]), {"reason": "Crew unavailable"}
    )
    assert response.status_code == 302
    job.refresh_from_db()
    assert job.status == "scheduled"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "reversed"


@pytest.mark.parametrize("action", ["job_reschedule", "job_cancel", "offer_withdraw"])
def test_completed_work_cannot_be_changed(client, team, completed_job, accepted_offer, action):
    client.force_login(team["admin"])
    pk = accepted_offer.pk if action == "offer_withdraw" else completed_job.pk
    response = client.post(reverse("operations:" + action, args=[pk]), reschedule_data(completed_job))
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "payable"


def test_reschedule_initial_values_fit_browser_datetime_input(client, team, job):
    client.force_login(team["admin"])
    response = client.get(reverse("operations:job_reschedule", args=[job.pk]))
    expected = timezone.localtime(job.scheduled_start).strftime("%Y-%m-%dT%H:%M")
    assert f'value="{expected}"' in response.content.decode()


def test_completed_job_is_not_an_upcoming_dashboard_appointment(client, team, completed_job):
    client.force_login(team["admin"])
    response = client.get(reverse("operations:dashboard"))
    assert not response.context["jobs"]
    metric = next(value for label, value, _, _ in response.context["metrics"] if label == "Upcoming jobs")
    assert metric == 0


def test_declined_offer_notification_stays_accessible_to_cleaner(client, team, job):
    from operations import services

    offer = services.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85")
    services.respond_to_offer(actor=team["cleaner"], offer=offer, accept=False)
    note = Notification.objects.get(recipient=team["cleaner"], kind="offer.rejected")
    client.force_login(team["cleaner"])
    assert client.get(note.link).status_code == 200
