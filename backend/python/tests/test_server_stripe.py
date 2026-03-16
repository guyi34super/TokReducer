"""Tests for Stripe endpoints."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

from tests.conftest import TEST_UID


def test_create_checkout_returns_400_if_already_pro(client, auth_headers, firestore_store):
    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
        "daily_requests": 0,
        "daily_reset_date": "2025-01-01",
    }

    with patch.dict(os.environ, {"STRIPE_SECRET_KEY": "sk_test", "STRIPE_PRICE_ID": "price_test"}), \
         patch("tokreducer.api.server._STRIPE_SECRET_KEY", "sk_test"), \
         patch("tokreducer.api.server._STRIPE_PRICE_ID", "price_test"):
        resp = client.post("/api/stripe/create-checkout", headers=auth_headers)

    assert resp.status_code == 400
    assert "Already on Pro" in resp.json()["detail"]


def test_create_checkout_returns_url(client, auth_headers, firestore_store):
    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "free",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "daily_requests": 0,
        "daily_reset_date": "2025-01-01",
    }

    mock_response = MagicMock()
    mock_response.json.return_value = {"url": "https://checkout.stripe.com/session123"}
    mock_response.raise_for_status.return_value = None

    async def fake_post(*args, **kwargs):
        return mock_response

    with patch("tokreducer.api.server._STRIPE_SECRET_KEY", "sk_test"), \
         patch("tokreducer.api.server._STRIPE_PRICE_ID", "price_test"), \
         patch("httpx.AsyncClient.post", side_effect=fake_post):
        resp = client.post("/api/stripe/create-checkout", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json()["url"] == "https://checkout.stripe.com/session123"


def test_webhook_upgrades_user(client, firestore_store):
    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "tier": "free",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
    }

    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": TEST_UID,
                "subscription": "sub_new",
                "customer": "cus_new",
            }
        },
    }
    body = json.dumps(event).encode()
    timestamp = str(int(time.time()))
    secret = "whsec_test"
    sig = hmac.HMAC(secret.encode(), f"{timestamp}.{body.decode()}".encode(), hashlib.sha256).hexdigest()

    with patch("tokreducer.api.server._STRIPE_WEBHOOK_SECRET", secret):
        resp = client.post(
            "/api/stripe/webhook",
            content=body,
            headers={
                "stripe-signature": f"t={timestamp},v1={sig}",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 200
    user = firestore_store.get(f"users/{TEST_UID}", {})
    assert user["tier"] == "pro"
    assert user["stripe_subscription_id"] == "sub_new"


def test_webhook_invalid_signature_returns_400(client, firestore_store):
    event = {"type": "checkout.session.completed", "data": {"object": {"client_reference_id": TEST_UID}}}
    body = json.dumps(event).encode()

    with patch("tokreducer.api.server._STRIPE_WEBHOOK_SECRET", "whsec_test"):
        resp = client.post(
            "/api/stripe/webhook",
            content=body,
            headers={
                "stripe-signature": "t=123,v1=badsig",
                "content-type": "application/json",
            },
        )

    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


def test_webhook_downgrade_on_cancel(client, firestore_store):
    firestore_store["users/uid-cancel"] = {
        "email": "cancel@example.com",
        "tier": "pro",
        "stripe_customer_id": "cus_cancel",
        "stripe_subscription_id": "sub_cancel",
    }

    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "customer": "cus_cancel",
                "status": "canceled",
            }
        },
    }
    body = json.dumps(event).encode()

    with patch("tokreducer.api.server._STRIPE_WEBHOOK_SECRET", ""):
        resp = client.post(
            "/api/stripe/webhook",
            content=body,
            headers={"content-type": "application/json"},
        )

    assert resp.status_code == 200
    user = firestore_store.get("users/uid-cancel", {})
    assert user["tier"] == "free"
