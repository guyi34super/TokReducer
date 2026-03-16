"""Tests for usage enforcement."""

from __future__ import annotations

from tests.conftest import TEST_UID


def test_usage_returns_free_tier_defaults(client, auth_headers):
    resp = client.get("/api/usage", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"
    assert data["used"] == 0
    assert data["limit"] == 2
    assert data["remaining"] == 2


def test_free_tier_limit_enforced(client, auth_headers, firestore_store):
    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 2,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "free",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "daily_requests": 0,
        "daily_reset_date": "2025-01-01",
    }

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 403
    assert "Free tier limit" in resp.json()["detail"]


def test_pro_tier_usage(client, auth_headers, firestore_store):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
        "daily_requests": 0,
        "daily_reset_date": today,
    }

    resp = client.get("/api/usage", headers=auth_headers)
    data = resp.json()
    assert data["tier"] == "pro"
    assert data["daily_used"] == 0
    assert data["daily_limit"] == 10


def test_pro_tier_daily_limit(client, auth_headers, firestore_store):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "pro",
        "stripe_customer_id": "cus_123",
        "stripe_subscription_id": "sub_123",
        "daily_requests": 10,
        "daily_reset_date": today,
    }

    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 429
    assert "Daily limit" in resp.json()["detail"]
