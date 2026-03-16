"""Tests for /api/config endpoints."""

from __future__ import annotations


def test_get_config_returns_defaults(client, auth_headers):
    resp = client.get("/api/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "openai"
    assert data["model"] == "gpt-4o"
    assert data["level"] == 2


def test_post_config_saves_and_returns(client, auth_headers):
    payload = {
        "provider": "anthropic",
        "api_key": "sk-test-12345678",
        "model": "claude-3",
        "level": 1,
        "upstream_url": "https://api.anthropic.com",
    }
    resp = client.post("/api/config", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "saved"

    resp2 = client.get("/api/config", headers=auth_headers)
    data = resp2.json()
    assert data["provider"] == "anthropic"
    assert data["model"] == "claude-3"
    assert data["level"] == 1


def test_api_key_is_masked_in_get(client, auth_headers):
    payload = {
        "provider": "openai",
        "api_key": "sk-abcdefghijklmnop",
        "model": "gpt-4o",
        "level": 2,
        "upstream_url": "https://api.openai.com",
    }
    client.post("/api/config", json=payload, headers=auth_headers)
    resp = client.get("/api/config", headers=auth_headers)
    key = resp.json()["api_key"]
    assert "..." in key
    assert key.startswith("sk-a")
    assert key.endswith("mnop")


def test_masked_key_preserves_real_key(client, auth_headers):
    real_key = "sk-abcdefghijklmnop"
    client.post(
        "/api/config",
        json={"provider": "openai", "api_key": real_key, "model": "gpt-4o", "level": 2, "upstream_url": "https://api.openai.com"},
        headers=auth_headers,
    )

    masked = client.get("/api/config", headers=auth_headers).json()["api_key"]
    client.post(
        "/api/config",
        json={"provider": "openai", "api_key": masked, "model": "gpt-4o", "level": 2, "upstream_url": "https://api.openai.com"},
        headers=auth_headers,
    )

    resp = client.get("/api/config", headers=auth_headers)
    key = resp.json()["api_key"]
    assert key.startswith("sk-a")
    assert key.endswith("mnop")
