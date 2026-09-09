"""Repeatable public browser checks: set FGK_E2E_BASE_URL to a running local server."""

import os
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = os.getenv("FGK_E2E_BASE_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(
    not BASE_URL, reason="Set FGK_E2E_BASE_URL to run browser checks against the local application."
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as runtime:
        instance = runtime.chromium.launch()
        yield instance
        instance.close()


@pytest.mark.parametrize(
    "width,height", [(320, 568), (375, 812), (390, 844), (768, 1024), (820, 1180), (1280, 800), (1440, 900)]
)
def test_public_pages_have_no_horizontal_overflow(browser, width, height):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        for path in ["/", "/residential/", "/commercial/", "/gallery/", "/quote/"]:
            response = page.goto(BASE_URL + path, wait_until="networkidle")
            assert response.status == 200
            assert page.locator("h1").count() == 1
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (
                f"Overflow at {width}: {path}"
            )
            if path == "/quote/":
                assert page.locator('button[type="submit"]').is_visible()
                for item in page.locator(
                    'input:not([type="hidden"],[type="checkbox"],[type="radio"],[name="website"]),textarea'
                ).all():
                    assert item.bounding_box()["width"] <= width
            if width in [320, 390, 768, 1440] and path in ["/", "/quote/"]:
                destination = Path(".local/screenshots")
                destination.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(destination / f"public-{width}-{'home' if path == '/' else 'quote'}.png"), full_page=True
                )
        assert not errors
    finally:
        page.close()


def test_mobile_menu_is_keyboard_operable(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(BASE_URL + "/")
        menu = page.get_by_role("button", name="Menu", exact=True)
        menu.focus()
        page.keyboard.press("Enter")
        assert menu.get_attribute("aria-expanded") == "true"
        assert page.get_by_role("navigation", name="Main navigation").is_visible()
        page.keyboard.press("Escape")
        assert menu.get_attribute("aria-expanded") == "false"
        assert menu.evaluate("node => node === document.activeElement")
    finally:
        page.close()


def test_gallery_filter_and_lightbox_keyboard(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    try:
        page.goto(BASE_URL + "/gallery/")
        page.locator(".filter-bar").get_by_role("link", name="Residential", exact=True).click()
        assert "category=residential" in page.url
        link = page.locator("[data-lightbox]").first
        link.focus()
        page.keyboard.press("Enter")
        assert page.get_by_role("dialog").is_visible()
        page.keyboard.press("ArrowRight")
        assert page.locator("#lightbox-count").inner_text() == "2 of 2"
        page.keyboard.press("Escape")
        assert not page.get_by_role("dialog").is_visible()
        assert link.evaluate("node => node === document.activeElement")
    finally:
        page.close()


def test_gallery_remains_useful_without_javascript(browser):
    page = browser.new_page(java_script_enabled=False, viewport={"width": 390, "height": 844})
    try:
        page.goto(BASE_URL + "/gallery/")
        page.locator(".filter-bar").get_by_role("link", name="Commercial", exact=True).click()
        assert "category=commercial" in page.url
        assert page.locator(".gallery-item").count() >= 1
        assert page.locator("[data-lightbox]").first.get_attribute("href").startswith("https://")
    finally:
        page.close()
