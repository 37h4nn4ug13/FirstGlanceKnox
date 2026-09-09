"""Opt-in browser coverage against an isolated Django test database, never demo records."""

import os
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(os.getenv("FGK_RUN_CREW_E2E") != "1", reason="Set FGK_RUN_CREW_E2E=1 for crew browser checks."),
]


@pytest.fixture
def crew_browser(monkeypatch):
    # Playwright's synchronous adapter holds an event loop in this thread.
    # Test ORM calls remain sequential; this override is never used by the app.
    monkeypatch.setenv("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        yield browser
        browser.close()


def signed_in_page(browser, client, live_server, user, width, height=900, javascript=True):
    client.force_login(user)
    context = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=javascript)
    context.add_cookies(
        [
            {
                "name": settings.SESSION_COOKIE_NAME,
                "value": client.cookies[settings.SESSION_COOKIE_NAME].value,
                "url": live_server.url,
            }
        ]
    )
    return context.new_page()


@pytest.mark.parametrize(
    "width,height", [(320, 568), (375, 812), (390, 844), (768, 1024), (820, 1180), (1280, 800), (1440, 900)]
)
def test_staff_and_customer_pages_fit_viewport(
    crew_browser, client, live_server, team, lead, invoice, accepted_offer, width, height
):
    paths = [
        ("admin", "/crew/"),
        ("admin", "/crew/customers/"),
        ("admin", "/crew/schedule/"),
        ("admin", reverse("operations:job_reschedule", args=[invoice.job_id])),
        ("admin", reverse("operations:job_cancel", args=[invoice.job_id])),
        ("admin", reverse("operations:offer_withdraw", args=[accepted_offer.pk])),
        ("admin", reverse("operations:invoice_detail", args=[invoice.pk])),
        ("sales", "/crew/leads/new/"),
        ("sales", reverse("operations:estimate_create", args=[lead.pk])),
        ("cleaner", reverse("operations:offer_detail", args=[accepted_offer.pk])),
        ("cleaner", reverse("operations:job_detail", args=[invoice.job_id])),
        ("customer", "/portal/"),
        ("customer", reverse("portal:invoice_account", args=[invoice.pk])),
    ]
    for role in ["admin", "sales", "cleaner", "customer"]:
        page = signed_in_page(crew_browser, client, live_server, team[role], width, height)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        try:
            for path in [path for actor, path in paths if actor == role]:
                response = page.goto(live_server.url + path, wait_until="load")
                assert response.status == 200, f"{role}: {path}"
                assert page.locator("h1").count() == 1, path
                overflow = page.evaluate("""() => [...document.querySelectorAll('main *')]
                    .filter(node => node.getBoundingClientRect().right > innerWidth + 1)
                    .slice(0, 8).map(node => ({tag: node.tagName, class: node.className,
                        width: node.getBoundingClientRect().width}))""")
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), (
                    f"{width}: {path}: {overflow}"
                )
                if width in [320, 1440] and path in ["/crew/", "/portal/"]:
                    destination = Path(".local/screenshots")
                    destination.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(destination / f"{role}-{width}.png"), full_page=True)
            assert not errors
        finally:
            page.context.close()


def test_mobile_menu_exposes_all_sections_with_keyboard(crew_browser, client, live_server, team):
    page = signed_in_page(crew_browser, client, live_server, team["admin"], 320, 568)
    try:
        page.goto(live_server.url + "/crew/")
        menu = page.locator(".mobile-menu summary")
        menu.focus()
        page.keyboard.press("Enter")
        panel = page.locator(".mobile-menu-panel")
        assert panel.is_visible()
        for name in ["Customers", "Estimates", "Invoices", "Compensation", "Price book", "Reports", "Audit history"]:
            assert panel.get_by_role("link", name=name, exact=False).count() == 1
        panel.get_by_role("link", name="Invoices", exact=False).click()
        assert page.url.endswith("/crew/invoices/")
        page.locator(".mobile-menu summary").click()
        page.keyboard.press("Escape")
        assert not page.locator(".mobile-menu-panel").is_visible()
        assert page.locator(".mobile-menu summary").evaluate("node => node === document.activeElement")
    finally:
        page.context.close()


def test_mobile_menu_works_without_javascript(crew_browser, client, live_server, team):
    page = signed_in_page(crew_browser, client, live_server, team["admin"], 390, javascript=False)
    try:
        page.goto(live_server.url + "/crew/")
        page.locator(".mobile-menu summary").click()
        page.locator(".mobile-menu-panel").get_by_role("link", name="Reports", exact=False).click()
        assert page.get_by_role("heading", level=1).inner_text() == "Business reports"
    finally:
        page.context.close()


def test_customer_sign_out_has_readable_contrast(crew_browser, client, live_server, team):
    page = signed_in_page(crew_browser, client, live_server, team["customer"], 390)
    try:
        page.goto(live_server.url + "/portal/")
        contrast = page.get_by_role("button", name="Sign out", exact=True).evaluate("""node => {
            const luminance = color => {
                const c = color.match(/[\\d.]+/g).slice(0, 3).map(v => {
                    v = Number(v) / 255;
                    return v <= .04045 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4;
                });
                return .2126*c[0] + .7152*c[1] + .0722*c[2];
            };
            const style = getComputedStyle(node), a = luminance(style.color), b = luminance(style.backgroundColor);
            return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
        }""")
        assert contrast >= 4.5
    finally:
        page.context.close()


@pytest.mark.parametrize("action", ["accept", "decline"])
def test_shared_estimate_response_passes_csrf(crew_browser, live_server, team, lead, price, action):
    from operations import services

    estimate = services.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    token = services.send_estimate(actor=team["sales"], estimate=estimate)
    page = crew_browser.new_page(viewport={"width": 390, "height": 844})
    url = live_server.url + reverse("portal:estimate", args=[token])
    try:
        page.goto(url)
        if action == "accept":
            page.get_by_label("Your full name").fill("Synthetic Customer")
            page.get_by_label("I approve this scope of work, price, and terms.").check()
            button = page.get_by_role("button", name="Approve estimate", exact=False)
        else:
            page.locator("summary").filter(has_text="Decline this estimate").click()
            page.get_by_label("Anything you'd like us to know?").fill("Please revise the scope")
            button = page.get_by_role("button", name="Decline estimate", exact=True)
        with page.expect_response(lambda response: response.url == url and response.request.method == "POST") as result:
            button.click()
        assert result.value.status == 200
        estimate.refresh_from_db()
        assert estimate.status == ("accepted" if action == "accept" else "declined")
    finally:
        page.context.close()


def test_admin_reschedules_from_mobile_job_screen(crew_browser, client, live_server, team, job, accepted_offer):
    from datetime import timedelta
    from django.utils import timezone

    page = signed_in_page(crew_browser, client, live_server, team["admin"], 390, 844)
    try:
        page.goto(live_server.url + reverse("operations:job_detail", args=[job.pk]))
        page.get_by_role("link", name="Reschedule appointment", exact=True).click()
        start = timezone.localtime(job.scheduled_start + timedelta(days=1))
        page.get_by_label("Start (Knoxville time)").fill(start.strftime("%Y-%m-%dT%H:%M"))
        page.get_by_label("Finish (Knoxville time)").fill((start + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M"))
        page.get_by_label("Reason for the schedule change").fill("Customer requested the following day")
        page.get_by_role("button", name="Save new appointment", exact=True).click()
        assert page.get_by_text("Appointment changed. Send new job offers", exact=False).is_visible()
        job.refresh_from_db()
        accepted_offer.refresh_from_db()
        assert job.status == "scheduled" and accepted_offer.status == "superseded"
    finally:
        page.context.close()


@pytest.mark.parametrize("width", [320, 390, 768, 1440])
def test_staff_and_planning_screens_are_responsive(crew_browser, client, live_server, team, lead, price, width):
    from operations import services
    from operations.models import AvailabilityBlock, RecurringPlan
    from django.utils import timezone

    estimate = services.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    token = services.send_estimate(actor=team["sales"], estimate=estimate)
    services.accept_estimate(estimate=estimate, token=token, signature="Synthetic Customer")
    plan = RecurringPlan.objects.create(
        customer=lead.customer,
        property=lead.property,
        estimate=estimate,
        name="Quarterly care",
        next_visit_at=timezone.now() + timezone.timedelta(days=30),
    )
    block = AvailabilityBlock.objects.create(
        starts_at=timezone.now() + timezone.timedelta(days=10), ends_at=timezone.now() + timezone.timedelta(days=11)
    )
    page = signed_in_page(crew_browser, client, live_server, team["admin"], width)
    try:
        paths = [
            reverse("accounts:staff"),
            reverse("accounts:staff_detail", args=[team["cleaner"].public_id]),
            reverse("accounts:staff_deactivate", args=[team["cleaner"].public_id]),
            reverse("accounts:staff_invite"),
            reverse("operations:block_edit", args=[block.pk]),
            reverse("operations:plan_edit", args=[plan.pk]),
            reverse("operations:schedule"),
            reverse("operations:estimate_revise", args=[estimate.pk]),
            reverse("operations:deliveries"),
        ]
        for path in paths:
            response = page.goto(live_server.url + path, wait_until="load")
            assert response.status == 200, path
            assert page.locator("h1").count() == 1
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), f"{width}: {path}"
            if width in [320, 1440] and path == reverse("accounts:staff_detail", args=[team["cleaner"].public_id]):
                page.screenshot(path=f".local/screenshots/staff-{width}.png", full_page=True)
    finally:
        page.context.close()


def test_admin_manages_employee_in_browser(crew_browser, client, live_server, team, settings):
    from accounts.models import User
    from django.core import mail
    import re

    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    page = signed_in_page(crew_browser, client, live_server, team["admin"], 390)
    try:
        page.goto(live_server.url + reverse("accounts:staff"))
        page.get_by_role("link", name="Invite employee", exact=True).click()
        page.get_by_label("Email", exact=False).fill("browser-employee@example.invalid")
        page.get_by_label("Display name", exact=False).fill("Browser Employee")
        page.get_by_label("Cleaner", exact=True).check()
        page.get_by_role("button", name="Create invitation", exact=False).click()
        assert page.get_by_role("heading", name="Browser Employee", exact=True).is_visible()
        page.get_by_label("Salesperson", exact=True).check()
        page.get_by_role("button", name="Save employee", exact=True).click()
        employee = User.objects.get(email="browser-employee@example.invalid")
        assert employee.groups.filter(name="Salesperson").exists()
        invitation_url = re.search(r"https?://\S+", mail.outbox[-1].body)[0]
        guest = crew_browser.new_page()
        try:
            guest.goto(invitation_url)
            guest.locator("#id_new_password1").fill("BrowserEmployeePassword!2026")
            guest.locator("#id_new_password2").fill("BrowserEmployeePassword!2026")
            guest.locator('form button[type="submit"]').click()
            employee.refresh_from_db()
            assert employee.is_active
        finally:
            guest.context.close()
        page.reload()
        page.get_by_role("link", name="Deactivate access", exact=True).click()
        page.get_by_label("Reason", exact=False).fill("Test employee departed")
        page.get_by_role("button", name="Deactivate employee", exact=True).click()
        employee.refresh_from_db()
        assert not employee.is_active
        assert page.get_by_role("button", name="Send new invitation", exact=True).is_visible()
    finally:
        page.context.close()


def test_admin_revises_estimate_with_extra_line(crew_browser, client, live_server, team, lead, price):
    from operations import services

    original = services.create_estimate(actor=team["admin"], lead=lead, lines=[{"price_book_item": price}])
    page = signed_in_page(crew_browser, client, live_server, team["admin"], 390)
    try:
        page.goto(live_server.url + reverse("operations:estimate_detail", args=[original.pk]))
        page.get_by_role("link", name="Revise estimate", exact=True).click()
        page.get_by_role("button", name="Add service line", exact=True).click()
        page.locator("#id_lines-6-description").fill("Extra window care")
        page.locator("#id_lines-6-quantity").fill("2")
        page.locator("#id_lines-6-unit_price").fill("10")
        page.get_by_label("Reason for revision", exact=False).fill("Customer requested extra windows")
        page.get_by_role("button", name="Save revision", exact=False).click()
        original.refresh_from_db()
        assert original.status == "superseded"
        assert original.revisions.get().total == 45
    finally:
        page.context.close()


def test_offline_queue_preserves_leads_added_during_sync(crew_browser, client, live_server, team):
    from operations.models import Lead

    page = signed_in_page(crew_browser, client, live_server, team["sales"], 390)
    try:
        page.goto(live_server.url + "/crew/leads/new/")
        page.context.set_offline(True)
        page.get_by_label("Service address", exact=False).fill("10 Offline Test Lane")
        page.get_by_label("Customer or business name", exact=False).fill("Offline Lead One")
        page.get_by_role("button", name="Save lead & visit", exact=False).click()
        assert page.get_by_role("heading", name="Device outbox").is_visible()
        inserted = False

        def append_while_sending(route):
            nonlocal inserted
            if not inserted:
                inserted = True
                page.evaluate("""() => {
                    const user=document.body.dataset.userId, key='fgk.outbox.'+user;
                    const queue=JSON.parse(localStorage.getItem(key));
                    queue.push({id:crypto.randomUUID(),user,kind:'lead',data:{name:'Offline Lead Two',address:'20 Offline Test Lane',kind:'residential',outcome:'interested'}});
                    localStorage.setItem(key,JSON.stringify(queue));
                }""")
            route.continue_()

        page.route("**/accounts/api/offline/", append_while_sending)
        page.context.set_offline(False)
        page.get_by_text("update(s) still waiting", exact=False).wait_for()
        assert Lead.objects.filter(customer__name="Offline Lead One").count() == 1
        assert page.locator("#device-outbox").inner_text().find("Offline Lead Two") >= 0
        page.get_by_role("button", name="Retry synchronization", exact=True).click()
        page.get_by_text("All queued updates are saved to the server.", exact=True).wait_for()
        assert Lead.objects.filter(customer__name="Offline Lead Two").count() == 1
    finally:
        page.context.close()


def test_offline_outbox_can_be_reviewed_and_discarded(crew_browser, client, live_server, team):
    page = signed_in_page(crew_browser, client, live_server, team["sales"], 390)
    try:
        page.goto(live_server.url + "/crew/leads/new/")
        page.context.set_offline(True)
        page.get_by_label("Service address", exact=False).fill("Unsent Test Address")
        page.get_by_role("button", name="Save lead & visit", exact=False).click()
        page.locator("#device-outbox summary").click()
        assert page.locator("#device-outbox").get_by_text("Unsent Test Address", exact=True).is_visible()
        page.on("dialog", lambda dialog: dialog.accept())
        page.get_by_role("button", name="Discard this update", exact=True).click()
        assert page.locator("#device-outbox").count() == 0
    finally:
        page.context.close()
