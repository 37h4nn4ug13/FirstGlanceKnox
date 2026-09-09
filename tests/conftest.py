from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone

from accounts.models import StaffProfile, User
from operations import services as s
from operations.models import PriceBookItem


@pytest.fixture(autouse=True)
def isolated_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture(autouse=True)
def fast_password_hashes(settings):
    # These tests exercise authorization and money; password algorithms are Django's responsibility.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]


@pytest.fixture
def team():
    users = {}
    for name, role in [
        ("admin", "Admin"),
        ("sales", "Salesperson"),
        ("cleaner", "Cleaner"),
        ("other_sales", "Salesperson"),
        ("other_cleaner", "Cleaner"),
    ]:
        user = User.objects.create_user(email=f"{name}@example.invalid", password="SyntheticTestPassword!2026")
        user.groups.add(Group.objects.get_or_create(name=role)[0])
        StaffProfile.objects.create(
            user=user, display_name=name, default_commission_rate=Decimal("10.00") if role == "Salesperson" else 0
        )
        users[name] = user
    users["customer"] = User.objects.create_user(
        email="customer@example.invalid", password="SyntheticCustomerPassword!2026"
    )
    return users


@pytest.fixture
def lead(team):
    result = s.capture_lead(
        actor=team["sales"],
        name="Synthetic Customer",
        email=team["customer"].email,
        address="100 Synthetic Lane",
        source="door_to_door",
    )
    result.customer.user = team["customer"]
    result.customer.save(update_fields=["user"])
    return result


@pytest.fixture
def price():
    return PriceBookItem.objects.create(name="Synthetic window service", unit_price=Decimal("25.00"))


@pytest.fixture
def estimate(team, lead, price):
    result = s.create_estimate(
        actor=team["sales"], lead=lead, lines=[{"price_book_item": price, "quantity": 8}], discount="0", tax_rate="0"
    )
    token = s.send_estimate(actor=team["sales"], estimate=result)
    return s.accept_estimate(estimate=result, signature="Synthetic Customer", token=token)


@pytest.fixture
def job(team, estimate):
    start = timezone.now() + timedelta(days=7)
    return s.schedule_job(
        actor=team["admin"], estimate=estimate, scheduled_start=start, scheduled_end=start + timedelta(hours=2)
    )


@pytest.fixture
def accepted_offer(team, job):
    offer = s.offer_job(actor=team["admin"], job=job, cleaner=team["cleaner"], fixed_amount="85.00")
    return s.respond_to_offer(actor=team["cleaner"], offer=offer, accept=True)


@pytest.fixture
def completed_job(team, job, accepted_offer):
    s.transition_job(actor=team["cleaner"], job=job, status="in_progress")
    s.transition_job(actor=team["cleaner"], job=job, status="completion_submitted", completed_checklist=job.checklist)
    return s.approve_completion(actor=team["admin"], job=job)


@pytest.fixture
def invoice(team, completed_job):
    return s.issue_invoice(actor=team["admin"], job=completed_job)
