from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from operations import planning, services
from operations.models import AccessToken, AuditEvent, AvailabilityBlock, Estimate, Job, OutboundMessage, RecurringPlan
from operations.tasks import deliver_message

pytestmark = pytest.mark.django_db


def test_revision_retires_original_links_without_changing_terms(team, lead, price):
    original = services.create_estimate(
        actor=team["sales"], lead=lead, lines=[{"price_book_item": price, "quantity": 2}]
    )
    token = services.send_estimate(actor=team["sales"], estimate=original)
    replacement = services.create_estimate(
        actor=team["sales"],
        lead=lead,
        supersedes=original,
        revision_reason="Customer reduced scope",
        lines=[{"price_book_item": price, "quantity": 1}],
    )
    original.refresh_from_db()
    assert original.status == "superseded" and original.total == Decimal("50.00")
    assert original.lines.get().quantity == 2
    assert replacement.total == Decimal("25.00") and replacement.supersedes == original
    assert AccessToken.objects.get(object_id=original.pk).revoked_at
    with pytest.raises(PermissionDenied):
        services.resolve_access_token(token, "estimate")
    with pytest.raises(ValidationError):
        services.create_estimate(
            actor=team["sales"],
            lead=lead,
            supersedes=original,
            revision_reason="Duplicate revision",
            lines=[{"price_book_item": price}],
        )


def test_accepted_estimate_cannot_be_revised(team, lead, price, estimate):
    with pytest.raises(ValidationError):
        services.create_estimate(
            actor=team["admin"],
            lead=lead,
            supersedes=estimate,
            revision_reason="Forbidden rewrite",
            lines=[{"price_book_item": price}],
        )
    assert Estimate.objects.count() == 1


def test_failed_revision_preserves_live_link(team, lead, price):
    original = services.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    token = services.send_estimate(actor=team["sales"], estimate=original)
    with pytest.raises(ValidationError):
        services.create_estimate(
            actor=team["sales"],
            lead=lead,
            supersedes=original,
            revision_reason="Scope update",
            lines=[{"price_book_item": price, "quantity": -1}],
        )
    assert services.resolve_access_token(token, "estimate").pk == original.pk


def test_revision_form_preserves_saved_rate_and_allows_deleting_lines(client, team, lead, price):
    original = services.create_estimate(
        actor=team["sales"], lead=lead, lines=[{"price_book_item": price, "quantity": 2}]
    )
    price.unit_price = 90
    price.save()
    client.force_login(team["sales"])
    url = reverse("operations:estimate_revise", args=[original.pk])
    response = client.get(url)
    assert response.context["line_forms"].initial[0]["unit_price"] == Decimal("25.00")
    response = client.post(
        url,
        {
            "discount": "0",
            "tax_rate": "0",
            "revision_reason": "Remove service and replace scope",
            "terms": "Updated scope",
            "lines-TOTAL_FORMS": "2",
            "lines-INITIAL_FORMS": "1",
            "lines-0-DELETE": "on",
            "lines-1-price_book_item": str(price.pk),
            "lines-1-quantity": "3",
            "lines-1-unit_price": "25.00",
            "lines-1-description": "Agreed windows",
        },
    )
    assert response.status_code == 302
    replacement = original.revisions.get()
    assert replacement.status == "review" and replacement.total == 75
    assert replacement.lines.count() == 1


def test_obsolete_email_is_not_sent_after_revision(team, lead, price, settings):
    from django.core import mail

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    original = services.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    services.send_estimate(actor=team["sales"], estimate=original)
    services.create_estimate(
        actor=team["sales"],
        lead=lead,
        supersedes=original,
        revision_reason="Correction",
        lines=[{"price_book_item": price}],
    )
    message = OutboundMessage.objects.get(dedupe_key=f"estimate:{original.pk}:v1")
    assert deliver_message(str(message.pk)) == "obsolete"
    assert not mail.outbox


def test_block_rejects_existing_appointment_and_remove_is_audited(team, job):
    values = {"staff": None, "starts_at": job.scheduled_start, "ends_at": job.scheduled_end, "reason": "Unavailable"}
    with pytest.raises(ValidationError):
        planning.save_block(actor=team["admin"], values=values)
    values.update(starts_at=job.scheduled_start + timedelta(days=2), ends_at=job.scheduled_end + timedelta(days=2))
    block = planning.save_block(actor=team["admin"], values=values)
    pk = block.pk
    planning.remove_block(actor=team["admin"], block=block, reason="Available again")
    assert not AvailabilityBlock.objects.filter(pk=pk).exists()
    assert AuditEvent.objects.filter(object_id=pk, action="availability.removed").exists()


@pytest.fixture
def plan(estimate):
    return RecurringPlan.objects.create(
        customer=estimate.customer,
        property=estimate.property,
        estimate=estimate,
        name="Repeat care",
        next_visit_at=timezone.now() + timedelta(days=40),
        interval_days=90,
    )


def test_recurring_pause_resume_and_duplicate_generation(team, plan):
    planning.save_plan(actor=team["admin"], plan=plan, values={"active": False})
    with pytest.raises(ValidationError):
        services.generate_recurring_visit(actor=team["admin"], plan=plan)
    planning.save_plan(actor=team["admin"], plan=plan, values={"active": True})
    expected = plan.next_visit_at
    job = services.generate_recurring_visit(actor=team["admin"], plan=plan, expected_visit=expected)
    assert job.status == "scheduled"
    with pytest.raises(ValidationError):
        services.generate_recurring_visit(actor=team["admin"], plan=plan, expected_visit=expected)
    assert Job.objects.filter(recurring_plan=plan).count() == 1


def test_recurring_conflict_does_not_advance_plan(team, plan):
    AvailabilityBlock.objects.create(starts_at=plan.next_visit_at, ends_at=plan.next_visit_at + timedelta(hours=4))
    original = plan.next_visit_at
    with pytest.raises(ValidationError):
        services.generate_recurring_visit(actor=team["admin"], plan=plan)
    plan.refresh_from_db()
    assert plan.next_visit_at == original


@pytest.mark.parametrize("role", ["sales", "cleaner", "customer"])
def test_planning_and_delivery_mutations_are_admin_only(client, team, plan, job, role):
    block = AvailabilityBlock.objects.create(starts_at=job.scheduled_start, ends_at=job.scheduled_end)
    client.force_login(team[role])
    for name, pk in [
        ("block_edit", block.pk),
        ("block_remove", block.pk),
        ("plan_edit", plan.pk),
        ("plan_generate", plan.pk),
    ]:
        response = client.post(reverse("operations:" + name, args=[pk]), {"reason": "Denied"})
        assert response.status_code == 403
    assert client.get(reverse("operations:deliveries")).status_code == 403
