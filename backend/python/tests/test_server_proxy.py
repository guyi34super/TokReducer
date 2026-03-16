"""Tests for /v1/chat/completions proxy endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from tests.conftest import TEST_UID


def _setup_user_with_key(firestore_store):
    """Pre-populate a user with an API key configured."""
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
        "api_key": "sk-test-key-12345678",
        "model": "gpt-4o",
        "level": 2,
        "upstream_url": "https://api.openai.com",
    }


def test_proxy_returns_400_without_api_key(client, auth_headers):
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "API key" in resp.json()["detail"]


def test_proxy_compresses_and_forwards(client, auth_headers, firestore_store):
    _setup_user_with_key(firestore_store)

    fake_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello!"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    with patch("tokreducer.api.server._proxy_openai", new_callable=AsyncMock) as mock_proxy:
        mock_proxy.return_value = ("Hello!", fake_response)
        resp = client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Say hello"}]},
            headers=auth_headers,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["choices"][0]["message"]["content"] == "Hello!"
    mock_proxy.assert_called_once()


def test_proxy_creates_log_entry(client, auth_headers, firestore_store):
    _setup_user_with_key(firestore_store)

    fake_response = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 1234567890,
        "model": "gpt-4o",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7},
    }

    with patch("tokreducer.api.server._proxy_openai", new_callable=AsyncMock) as mock_proxy:
        mock_proxy.return_value = ("Hi", fake_response)
        client.post(
            "/v1/chat/completions",
            json={"model": "gpt-4o", "messages": [{"role": "user", "content": "Hello"}]},
            headers=auth_headers,
        )

    log_keys = [k for k in firestore_store if k.startswith(f"users/{TEST_UID}/logs/")]
    assert len(log_keys) >= 1
    log = firestore_store[log_keys[0]]
    assert log["endpoint"] == "/v1/chat/completions"
    assert log["status"] == "ok"


def test_proxy_injects_system_prompt(client, auth_headers, firestore_store):
    _setup_user_with_key(firestore_store)

    captured_messages = []

    async def capture_proxy(upstream_url, api_key, model, messages, body):
        captured_messages.extend(messages)
        return ("OK", {
            "id": "test", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        })

    with patch("tokreducer.api.server._proxy_openai", side_effect=capture_proxy):
        client.post(
            "/v1/chat/completions",
            json={"messages": [{"role": "user", "content": "test message"}]},
            headers=auth_headers,
        )

    roles = [m["role"] for m in captured_messages]
    assert "system" in roles


def test_proxy_increments_usage(client, auth_headers, firestore_store):
    _setup_user_with_key(firestore_store)

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

    user_data = firestore_store.get(f"users/{TEST_UID}", {})
    assert user_data.get("requests_used", 0) >= 1
