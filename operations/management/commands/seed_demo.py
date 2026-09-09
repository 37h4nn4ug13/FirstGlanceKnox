import os
import secrets
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import StaffProfile
from operations import services as s
from operations.models import Customer, Estimate, JobOffer, PriceBookItem, Property, RecurringPlan, ScheduleLock


class Command(BaseCommand):
    help = "Create isolated synthetic demo records. Runs only with DEBUG=true."

    @transaction.atomic
    def handle(self, **options):
        if not settings.DEBUG:
            raise CommandError("Demo data is disabled outside DEBUG development.")
        User = get_user_model()
        if User.objects.filter(email="admin@demo.invalid").exists():
            self.stdout.write("Demo already exists. Existing records and passwords were preserved.")
            return
        password = os.getenv("DEMO_PASSWORD") or secrets.token_urlsafe(18)
        groups = {name: Group.objects.get_or_create(name=name)[0] for name in ["Admin", "Salesperson", "Cleaner"]}
        groups["Admin"].permissions.set(Permission.objects.all())
        for name, allowed in [
            (
                "Salesperson",
                [
                    "add_lead",
                    "view_lead",
                    "change_lead",
                    "add_estimate",
                    "view_estimate",
                    "view_job",
                    "view_commissionentry",
                ],
            ),
            ("Cleaner", ["view_job", "view_joboffer", "view_cleanerpayout", "add_jobevidence"]),
        ]:
            groups[name].permissions.set(Permission.objects.filter(codename__in=allowed))

        def staff(email, first, last, roles, superuser=False):
            user = User.objects.create_user(
                email=email,
                password=password,
                first_name=first,
                last_name=last,
                is_staff=superuser,
                is_superuser=superuser,
            )
            user.groups.add(*(groups[role] for role in roles))
            StaffProfile.objects.create(
                user=user,
                display_name=f"{first} {last}",
                default_commission_rate=Decimal("10.00") if "Salesperson" in roles else 0,
            )
            return user

        admin = staff("admin@demo.invalid", "Ethan", "Demo", ["Admin"], True)
        sales = staff("sales@demo.invalid", "Jordan", "Demo", ["Salesperson"])
        cleaner = staff("cleaner@demo.invalid", "Taylor", "Demo", ["Cleaner"])
        staff("crew@demo.invalid", "Casey", "Demo", ["Salesperson", "Cleaner"])
        customer_user = User.objects.create_user(
            email="customer@demo.invalid", password=password, first_name="Avery", last_name="Demo"
        )
        ScheduleLock.objects.get_or_create(pk=1)
        items = []
        for name, unit, rate in [
            ("Exterior window cleaning", "window", "9.00"),
            ("Interior window cleaning", "window", "7.00"),
            ("Screen cleaning", "screen", "4.00"),
            ("Tracks and sills", "window", "3.00"),
            ("Commercial glass care", "visit", "260.00"),
            ("Hard-water treatment", "pane", "18.00"),
        ]:
            item, _ = PriceBookItem.objects.get_or_create(
                name=name,
                defaults={
                    "unit": unit,
                    "unit_price": rate,
                    "description": "Synthetic demo pricing. Replace with approved business pricing before use.",
                },
            )
            items.append(item)
        now = timezone.now()
        examples = [
            ("Avery Morgan", "residential", -12, "paid"),
            ("Oak & Elm Studio", "commercial", -8, "partial"),
            ("Sam Bennett", "residential", -3, "review"),
            ("Rowan Ellis", "residential", 1, "accepted"),
            ("Cedar Corner Offices", "commercial", 2, "offered"),
            ("Riley Parker", "residential", 3, "rejected"),
            ("Peyton Lane", "residential", 4, "draft"),
            ("Riverbend Retail", "commercial", 5, "sent"),
            ("Jamie Brooks", "residential", 6, "declined"),
            ("Alex Quinn", "residential", -20, "overdue"),
            ("Cameron Reed", "residential", -18, "void"),
            ("Juniper House", "residential", 7, "expired"),
        ]
        for i, (name, kind, days, state) in enumerate(examples):
            start = (now + timezone.timedelta(days=days)).replace(hour=14, minute=0, second=0, microsecond=0)
            moment = min(now, start - timezone.timedelta(days=1))
            with patch("operations.services.timezone.now", return_value=moment):
                lead = s.capture_lead(
                    actor=sales,
                    name=name,
                    address=f"{100 + i} Demonstration Lane",
                    email=f"customer{i}@demo.invalid",
                    phone="",
                    kind=kind,
                    source="referral" if i % 2 else "door_to_door",
                    message="Synthetic demo record. No real customer or property.",
                    outcome="interested",
                )
                if i == 0:
                    lead.customer.user = customer_user
                    lead.customer.save(update_fields=["user"])
                estimate = s.create_estimate(
                    actor=sales,
                    lead=lead,
                    lines=[
                        {
                            "price_book_item": items[4] if kind == "commercial" else items[0],
                            "quantity": 1 if kind == "commercial" else 24,
                        },
                        {"price_book_item": items[2], "quantity": 12},
                    ],
                    discount=0,
                    tax_rate=0,
                )
                if estimate.status == "review":
                    s.approve_estimate(actor=admin, estimate=estimate)
                if state == "draft":
                    continue
                token = s.send_estimate(actor=sales, estimate=estimate)
                if state == "sent":
                    continue
                if state == "declined":
                    s.decline_estimate(
                        actor=None, estimate=estimate, token=token, reason="Demo customer postponed service."
                    )
                    continue
                estimate = s.accept_estimate(actor=None, estimate=estimate, token=token, signature=name)
                job = s.schedule_job(
                    actor=sales,
                    estimate=estimate,
                    scheduled_start=start,
                    scheduled_end=start + timezone.timedelta(hours=2),
                )
                offer = s.offer_job(
                    actor=admin,
                    job=job,
                    cleaner=cleaner,
                    fixed_amount=Decimal("110.00") if kind == "residential" else Decimal("145.00"),
                )
                if state == "offered":
                    continue
                if state == "expired":
                    JobOffer.objects.filter(pk=offer.pk).update(
                        status="expired", expires_at=now - timezone.timedelta(hours=1)
                    )
                    s._refresh_assignment_status(job)
                    continue
                if state == "rejected":
                    s.respond_to_offer(actor=cleaner, offer=offer, accept=False, reason="Demo scheduling conflict.")
                    continue
                s.respond_to_offer(actor=cleaner, offer=offer, accept=True)
                if state == "accepted":
                    continue
                s.transition_job(actor=cleaner, job=job, status="in_progress")
                s.transition_job(
                    actor=cleaner,
                    job=job,
                    status="completion_submitted",
                    completed_checklist=job.checklist,
                    notes="Demo: scope completed and glass inspected.",
                )
                if state == "review":
                    continue
                s.approve_completion(actor=admin, job=job)
                invoice = s.issue_invoice(
                    actor=admin,
                    job=job,
                    due_date=(now - timezone.timedelta(days=5)).date()
                    if state == "overdue"
                    else (now + timezone.timedelta(days=14)).date(),
                    purchase_order="DEMO-PO-01" if kind == "commercial" else "",
                )
                if state in ["paid", "partial"]:
                    s.record_payment(
                        actor=admin,
                        invoice=invoice,
                        amount=invoice.total if state == "paid" else Decimal("100.00"),
                        method="check",
                        reference="DEMO only",
                    )
                if state == "paid":
                    payout = offer.payouts.get(status="payable")
                    s.mark_payout_paid(actor=admin, payout=payout, reference="DEMO payout")
                    commission = invoice.commissions.get(status="earned")
                    s.mark_commission_paid(actor=admin, entry=commission, reference="DEMO commission")
                if state == "void":
                    s.void_invoice(actor=admin, invoice=invoice, reason="Demo canceled billing example.")
        commercial = Customer.objects.filter(kind="commercial").first()
        Property.objects.create(
            customer=commercial,
            name="Second demonstration location",
            address_line1="220 Sample Plaza",
            city="Knoxville",
            kind="commercial",
        )
        accepted = Estimate.objects.filter(customer=commercial, status="accepted").first()
        if accepted:
            RecurringPlan.objects.create(
                customer=commercial,
                property=accepted.property,
                estimate=accepted,
                name="Quarterly commercial care (demo)",
                interval_days=90,
                next_visit_at=now + timezone.timedelta(days=90),
            )
        directory = Path(settings.BASE_DIR) / ".local"
        directory.mkdir(exist_ok=True)
        (directory / "demo-access.txt").write_text(
            "LOCAL DEMO ACCESS — do not publish\n\nWebsite: http://127.0.0.1:8765/\nLogin: http://127.0.0.1:8765/accounts/login/\n\nAccounts:\nadmin@demo.invalid — Administration\nsales@demo.invalid — Salesperson\ncleaner@demo.invalid — Cleaner\ncrew@demo.invalid — Salesperson + Cleaner\ncustomer@demo.invalid — Customer portal\n\nPassword for these demo accounts: "
            + password
            + "\n",
            encoding="utf-8",
        )
        self.stdout.write(self.style.SUCCESS("Synthetic demo created. Private login details: .local/demo-access.txt"))
