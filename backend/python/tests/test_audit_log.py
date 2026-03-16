"""Tests for audit logging functionality."""

from __future__ import annotations

import json
import hashlib
import hmac as hmac_mod
import time
from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_UID


def test_config_save_creates_audit_entry(client, auth_headers, firestore_store):
    payload = {
        "provider": "openai",
        "api_key": "sk-test-12345678",
        "model": "gpt-4o",
        "level": 2,
        "upstream_url": "https://api.openai.com",
    }
    client.post("/api/config", json=payload, headers=auth_headers)

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "config.save" in actions


def test_agreement_accept_creates_audit_entry(client, auth_headers, firestore_store):
    client.post("/api/agreement", headers=auth_headers)

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "agreement.accept" in actions


def test_compress_creates_audit_entry(client, auth_headers, firestore_store):
    client.post("/compress", json={"prompt": "hello world", "level": 2}, headers=auth_headers)

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "compress" in actions


def test_audit_entry_contains_ip_and_ua(client, auth_headers, firestore_store):
    client.post(
        "/compress",
        json={"prompt": "test", "level": 1},
        headers={**auth_headers, "user-agent": "TestBot/1.0"},
    )

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    assert len(audit_keys) > 0
    entry = firestore_store[audit_keys[0]]
    assert "ip" in entry
    assert entry["user_agent"] == "TestBot/1.0"
    assert "timestamp" in entry


def test_proxy_success_creates_audit_entry(client, auth_headers, firestore_store):
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
        "requests_used": 0,
        "agreement_accepted_at": "2025-01-01",
        "created_at": "2025-01-01",
        "tier": "free",
        "stripe_customer_id": None,
        "stripe_subscription_id": None,
        "daily_requests": 0,
        "daily_reset_date": today,
    }
    firestore_store[f"users/{TEST_UID}/config/current"] = {
        "provider": "openai",
        "api_key": "sk-test",
        "model": "gpt-4o",
        "level": 2,
        "upstream_url": "https://api.openai.com",
    }

    fake_response = {
        "id": "test", "object": "chat.completion", "created": 0, "model": "gpt-4o",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }

    with patch("tokreducer.api.server._proxy_openai", new_callable=AsyncMock) as mock_proxy:
        mock_proxy.return_value = ("Hi", fake_response)
        client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers=auth_headers,
        )

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "proxy.success" in actions


def test_stripe_webhook_creates_audit_entry(client, firestore_store):
    firestore_store[f"users/{TEST_UID}"] = {
        "email": "test@example.com",
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

    with patch("tokreducer.api.server._STRIPE_WEBHOOK_SECRET", ""):
        client.post(
            "/api/stripe/webhook",
            content=body,
            headers={"content-type": "application/json"},
        )

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "stripe.upgrade" in actions


def test_usage_view_creates_audit_entry(client, auth_headers, firestore_store):
    client.get("/api/usage", headers=auth_headers)

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "usage.view" in actions


def test_subscription_view_creates_audit_entry(client, auth_headers, firestore_store):
    client.get("/api/subscription", headers=auth_headers)

    audit_keys = [k for k in firestore_store if f"users/{TEST_UID}/audit_logs/" in k]
    actions = [firestore_store[k]["action"] for k in audit_keys]
    assert "subscription.view" in actions
