"""Behavioral tests for the authoritative lead-to-payment lifecycle."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from accounts.models import StaffProfile
from operations import services as s
from operations.models import (
    AccessToken,
    AvailabilityBlock,
    CleanerPayout,
    CommissionEntry,
    Customer,
    Estimate,
    Job,
    JobOffer,
    Lead,
    Notification,
    OutboundMessage,
    Payment,
    Property,
)

pytestmark = pytest.mark.django_db


def test_complete_lifecycle_separates_cleaner_pay_and_commission(team, invoice, accepted_offer):
    payout = CleanerPayout.objects.get(offer=accepted_offer)
    entry = CommissionEntry.objects.get(invoice=invoice)
    assert payout.status == "payable"
    assert payout.amount == Decimal("85.00")
    assert entry.status == "pending"
    assert entry.amount == Decimal("20.00")
    s.record_payment(actor=team["admin"], invoice=invoice, amount="75.00", method="check")
    invoice.refresh_from_db()
    entry.refresh_from_db()
    assert invoice.status == "partial" and invoice.balance == Decimal("125.00")
    assert entry.status == "pending"
    s.mark_payout_paid(actor=team["admin"], payout=payout, reference="SYNTHETIC-PAYOUT")
    s.record_payment(actor=team["admin"], invoice=invoice, amount="125.00", method="cash")
    invoice.refresh_from_db()
    entry.refresh_from_db()
    payout.refresh_from_db()
    assert invoice.status == "paid" and invoice.balance == 0
    assert entry.status == "earned"
    assert payout.status == "paid"
    s.mark_commission_paid(actor=team["admin"], entry=entry, reference="SYNTHETIC-COMMISSION")
    entry.refresh_from_db()
    assert entry.status == "paid"


def test_price_and_commission_profile_changes_do_not_rewrite_accepted_terms(team, estimate, price, invoice):
    price.unit_price = Decimal("999.00")
    price.save(update_fields=["unit_price"])
    StaffProfile.objects.filter(user=team["sales"]).update(default_commission_rate="40.00")
    estimate.refresh_from_db()
    assert estimate.accepted_snapshot["total"] == "200.00"
    assert estimate.accepted_snapshot["commission_rate"] == "10.00"
    assert estimate.accepted_snapshot["lines"][0]["unit_price"] == "25.00"
    assert invoice.total == Decimal("200.00")
    entry = CommissionEntry.objects.get(invoice=invoice)
    assert entry.rate_snapshot == Decimal("10.00") and entry.amount == Decimal("20.00")


def test_rejected_offer_preserves_history_and_can_be_reassigned(team, job):
    rejected = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85.00")
    s.respond_to_offer(actor=team["cleaner"], offer=rejected, accept=False, reason="Unavailable")
    replacement = s.offer_job(actor=team["admin"], job=job, cleaner=team["other_cleaner"], fixed_amount="90.00")
    s.respond_to_offer(actor=team["other_cleaner"], offer=replacement, accept=True)
    rejected.refresh_from_db()
    assert rejected.status == "rejected" and rejected.rejection_reason == "Unavailable"
    assert job.offers.count() == 2
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=rejected, accept=True)


def test_stale_expired_and_withdrawn_offers_cannot_be_accepted(team, job):
    offer = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85.00")
    JobOffer.objects.filter(pk=offer.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=offer, accept=True)
    JobOffer.objects.filter(pk=offer.pk).update(expires_at=timezone.now() + timedelta(hours=1))
    s.withdraw_offer(actor=team["admin"], offer=offer, reason="Appointment review")
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=offer, accept=True)


def test_double_acceptance_creates_one_payout(team, accepted_offer):
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=accepted_offer, accept=True)
    assert CleanerPayout.objects.filter(offer=accepted_offer).count() == 1


def test_material_schedule_change_requires_fresh_acceptance(team, job, accepted_offer):
    start = job.scheduled_start + timedelta(days=1)
    s.reschedule_job(
        actor=team["admin"],
        job=job,
        scheduled_start=start,
        scheduled_end=start + timedelta(hours=2),
        reason="Customer requested new day",
    )
    accepted_offer.refresh_from_db()
    assert accepted_offer.status == "superseded"
    assert accepted_offer.accepted_terms["fixed_amount"] == "85.00"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "reversed"
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=accepted_offer, accept=True)
    new = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="95.00")
    assert new.status == "offered"
    assert CleanerPayout.objects.filter(status="pending").count() == 0


def test_scope_tampering_is_detected_at_offer_acceptance(team, job):
    offer = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85.00")
    Job.objects.filter(pk=job.pk).update(scope="Materially changed scope")
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=offer, accept=True)


def test_time_off_blocks_offer_acceptance(team, job):
    AvailabilityBlock.objects.create(
        staff=team["cleaner"], starts_at=job.scheduled_start, ends_at=job.scheduled_end, reason="Synthetic time off"
    )
    offer = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85")
    with pytest.raises(ValidationError):
        s.respond_to_offer(actor=team["cleaner"], offer=offer, accept=True)


def test_completion_requires_checklist_and_admin_approval(team, job, accepted_offer):
    s.transition_job(actor=team["cleaner"], job=job, status="in_progress")
    with pytest.raises(ValidationError):
        s.transition_job(actor=team["cleaner"], job=job, status="completion_submitted")
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "pending"
    s.transition_job(actor=team["cleaner"], job=job, status="completion_submitted", completed_checklist=job.checklist)
    with pytest.raises(PermissionDenied):
        s.approve_completion(actor=team["cleaner"], job=job)
    s.approve_completion(actor=team["admin"], job=job, approved=False, reason="Please review the side window")
    job.refresh_from_db()
    assert job.status == "in_progress"
    assert CleanerPayout.objects.get(offer=accepted_offer).status == "pending"


def test_invoice_issue_and_payment_retry_are_idempotent(team, invoice, completed_job):
    second = s.issue_invoice(actor=team["admin"], job=completed_job)
    assert second.pk == invoice.pk and second.number == invoice.number
    first_payment = s.record_payment(
        actor=team["admin"], invoice=invoice, amount="25", idempotency_key="synthetic-payment"
    )
    retry = s.record_payment(actor=team["admin"], invoice=invoice, amount="25", idempotency_key="synthetic-payment")
    assert retry.pk == first_payment.pk
    invoice.refresh_from_db()
    assert invoice.paid_amount == Decimal("25.00")
    with pytest.raises(ValidationError):
        s.record_payment(actor=team["admin"], invoice=invoice, amount="50", idempotency_key="synthetic-payment")


def test_payment_reversal_preserves_adjustments_and_unearns_commission(team, invoice):
    payment = s.record_payment(actor=team["admin"], invoice=invoice, amount=invoice.total)
    entry = CommissionEntry.objects.get(invoice=invoice)
    assert entry.status == "earned"
    reversal = s.reverse_payment(actor=team["admin"], payment=payment, reason="Synthetic correction")
    invoice.refresh_from_db()
    entry.refresh_from_db()
    assert invoice.balance == Decimal("200.00") and invoice.status == "issued"
    assert reversal.amount == Decimal("-200.00") and reversal.reversal_of_id == payment.pk
    assert entry.status == "reversed"
    assert CommissionEntry.objects.get(reversal_of=entry).amount == Decimal("-20.00")
    assert Payment.objects.filter(invoice=invoice).count() == 2
    with pytest.raises(ValidationError):
        s.reverse_payment(actor=team["admin"], payment=payment, reason="Already reversed")


def test_invalid_money_and_overpayment_are_rejected(team, invoice):
    for invalid in ["NaN", "Infinity", "-Infinity", "not-money"]:
        with pytest.raises(ValidationError):
            s.money(invalid)
    for invalid in ["0", "-1", "200.01"]:
        with pytest.raises(ValidationError):
            s.record_payment(actor=team["admin"], invoice=invoice, amount=invalid)
    assert s.money("1.005") == Decimal("1.01")
    assert invoice.payments.count() == 0


def test_void_requires_reversing_payments(team, invoice):
    payment = s.record_payment(actor=team["admin"], invoice=invoice, amount="25")
    with pytest.raises(ValidationError):
        s.void_invoice(actor=team["admin"], invoice=invoice, reason="Replaced")
    s.reverse_payment(actor=team["admin"], payment=payment, reason="Replaced invoice")
    s.void_invoice(actor=team["admin"], invoice=invoice, reason="Replaced invoice")
    invoice.refresh_from_db()
    assert invoice.status == "void" and invoice.issued_snapshot["total"] == "200.00"


def test_object_authorization_hides_unrelated_customer_data(team, lead, job, accepted_offer, invoice):
    assert not s.leads_for(team["other_sales"]).filter(pk=lead.pk).exists()
    assert not s.customers_for(team["other_cleaner"]).filter(pk=lead.customer_id).exists()
    assert not s.jobs_for(team["other_cleaner"]).filter(pk=job.pk).exists()
    assert not s.invoices_for(team["sales"]).filter(pk=invoice.pk).exists()
    assert s.jobs_for(team["cleaner"]).filter(pk=job.pk).exists()
    assert s.invoices_for(team["customer"]).filter(pk=invoice.pk).exists()
    with pytest.raises(PermissionDenied):
        s.require_lead(team["other_sales"], lead)
    with pytest.raises(PermissionDenied):
        s.respond_to_offer(actor=team["other_cleaner"], offer=accepted_offer, accept=True)
    with pytest.raises(PermissionDenied):
        s.transition_job(actor=team["other_cleaner"], job=job, status="in_progress")


def test_financial_actions_are_admin_only(team, job, invoice, accepted_offer):
    payout = CleanerPayout.objects.get(offer=accepted_offer)
    entry = CommissionEntry.objects.get(invoice=invoice)
    for actor in [team["sales"], team["cleaner"], team["customer"]]:
        with pytest.raises(PermissionDenied):
            s.record_payment(actor=actor, invoice=invoice, amount="10")
        with pytest.raises(PermissionDenied):
            s.mark_commission_paid(actor=actor, entry=entry, reference="forbidden")
        with pytest.raises(PermissionDenied):
            s.mark_payout_paid(actor=actor, payout=payout, reference="forbidden")
        with pytest.raises(PermissionDenied):
            s.offer_job(actor=actor, job=job, cleaner=team["cleaner"], fixed_amount="100")


def test_tokens_are_hashed_expiring_revocable_and_purpose_scoped(team, lead, price):
    estimate = s.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    token = s.send_estimate(actor=team["sales"], estimate=estimate)
    assert s.resolve_access_token(token, "estimate").pk == estimate.pk
    assert not AccessToken.objects.filter(secret_hash=token).exists()
    with pytest.raises(PermissionDenied):
        s.resolve_access_token(token, "invoice")
    with pytest.raises(PermissionDenied):
        s.accept_estimate(actor=team["other_sales"], estimate=estimate, signature="Impostor")
    AccessToken.objects.filter(object_id=estimate.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(PermissionDenied):
        s.resolve_access_token(token, "estimate")
    new_token = s.create_access_token(actor=team["sales"], obj=estimate)
    s.revoke_access_tokens(actor=team["admin"], obj=estimate)
    with pytest.raises(PermissionDenied):
        s.resolve_access_token(new_token, "estimate")


def test_price_exceptions_require_admin_approval(team, lead, price):
    estimate = s.create_estimate(
        actor=team["sales"], lead=lead, lines=[{"price_book_item": price, "unit_price": "10.00"}]
    )
    assert estimate.status == "review"
    with pytest.raises(ValidationError):
        s.send_estimate(actor=team["sales"], estimate=estimate)
    with pytest.raises(PermissionDenied):
        s.approve_estimate(actor=team["sales"], estimate=estimate)
    approved = s.approve_estimate(actor=team["admin"], estimate=estimate)
    assert approved.status == "draft"


def test_failed_estimate_rolls_back_lines_and_header(team, lead, price):
    with pytest.raises(ValidationError):
        s.create_estimate(
            actor=team["sales"],
            lead=lead,
            lines=[{"price_book_item": price}, {"price_book_item": price, "quantity": "-1"}],
        )
    assert Estimate.objects.count() == 0


def test_booking_cannot_double_book_accepted_estimate(team, estimate, job):
    with pytest.raises(ValidationError):
        s.schedule_job(
            actor=team["sales"], estimate=estimate, scheduled_start=job.scheduled_start, scheduled_end=job.scheduled_end
        )
    assert Job.objects.count() == 1


def test_notification_and_estimate_email_deduplicate(team, lead, price):
    estimate = s.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    s.send_estimate(actor=team["sales"], estimate=estimate)
    s.send_estimate(actor=team["sales"], estimate=estimate)
    assert OutboundMessage.objects.filter(dedupe_key=f"estimate:{estimate.pk}:v1").count() == 1
    for _ in range(3):
        s.notify(recipient=team["cleaner"], kind="test", title="A generic update", dedupe_key="synthetic-event")
    assert Notification.objects.filter(dedupe_key="synthetic-event").count() == 1


def test_do_not_contact_and_lead_deduplication(team, lead):
    duplicate = s.capture_lead(
        actor=team["sales"], name="Synthetic Customer", email=lead.customer.email, address="100 Synthetic Lane"
    )
    assert duplicate.customer_id == lead.customer_id and duplicate.property_id == lead.property_id
    assert Customer.objects.count() == Property.objects.count() == 1
    s.record_visit(actor=team["sales"], lead=lead, outcome="do_not_contact", notes="Synthetic preference")
    with pytest.raises(ValidationError):
        s.capture_lead(name="Synthetic Customer", email=lead.customer.email, address="100 Synthetic Lane")
    assert Lead.objects.count() == 2


def test_role_combination_and_inactive_staff(team):
    team["sales"].groups.add(Group.objects.get(name="Cleaner"))
    assert s.has_role(team["sales"], "Salesperson") and s.has_role(team["sales"], "Cleaner")
    team["sales"].staff_profile.is_active = False
    team["sales"].staff_profile.save(update_fields=["is_active"])
    assert not s.has_role(team["sales"], "Salesperson", "Cleaner")
