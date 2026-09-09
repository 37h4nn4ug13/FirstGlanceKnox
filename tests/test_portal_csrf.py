import re

import pytest
from django.test import Client
from django.urls import reverse

from operations import services

pytestmark = pytest.mark.django_db


@pytest.fixture
def shared_estimate(team, lead, price):
    estimate = services.create_estimate(actor=team["sales"], lead=lead, lines=[{"price_book_item": price}])
    token = services.send_estimate(actor=team["sales"], estimate=estimate)
    return estimate, reverse("portal:estimate", args=[token])


@pytest.mark.parametrize("origin", ["https://unrelated.example", "null"])
def test_shared_link_still_rejects_foreign_origins(shared_estimate, origin):
    estimate, url = shared_estimate
    client = Client(enforce_csrf_checks=True)
    response = client.get(url)
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode())[1]
    response = client.post(
        url,
        {
            "csrfmiddlewaretoken": token,
            "action": "accept",
            "signature": "Synthetic Customer",
            "agreement": "on",
        },
        HTTP_ORIGIN=origin,
    )
    assert response.status_code == 403
    estimate.refresh_from_db()
    assert estimate.status in ["sent", "viewed"]


def test_shared_link_still_requires_csrf_token(shared_estimate):
    estimate, url = shared_estimate
    client = Client(enforce_csrf_checks=True)
    client.get(url)
    response = client.post(
        url,
        {
            "action": "accept",
            "signature": "Synthetic Customer",
            "agreement": "on",
        },
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code == 403
    estimate.refresh_from_db()
    assert estimate.status in ["sent", "viewed"]


def test_shared_link_allows_valid_same_origin_approval(shared_estimate):
    estimate, url = shared_estimate
    client = Client(enforce_csrf_checks=True)
    response = client.get(url)
    assert response["Referrer-Policy"] == "same-origin"
    assert "no-store" in response["Cache-Control"]
    token = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', response.content.decode())[1]
    response = client.post(
        url,
        {
            "csrfmiddlewaretoken": token,
            "action": "accept",
            "signature": "Synthetic Customer",
            "agreement": "on",
        },
        HTTP_ORIGIN="http://testserver",
    )
    assert response.status_code == 200
    estimate.refresh_from_db()
    assert estimate.status == "accepted"
