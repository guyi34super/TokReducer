"""Tests for authentication middleware."""

from __future__ import annotations

from unittest.mock import patch


def test_missing_auth_header_returns_401(client):
    resp = client.get("/api/config")
    assert resp.status_code == 401
    assert "Authorization" in resp.json()["detail"]


def test_malformed_bearer_returns_401(client):
    resp = client.get("/api/config", headers={"Authorization": "Token abc"})
    assert resp.status_code == 401


def test_invalid_token_returns_401(client, mocks):
    mocks["auth"].verify_id_token.side_effect = Exception("expired")
    resp = client.get("/api/config", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower() or "invalid" in resp.json()["detail"].lower()


def test_valid_token_allows_access(client, auth_headers):
    resp = client.get("/api/config", headers=auth_headers)
    assert resp.status_code == 200


def test_public_paths_skip_auth(client):
    for path in ["/health", "/docs", "/openapi.json"]:
        resp = client.get(path)
        assert resp.status_code in (200, 307), f"{path} returned {resp.status_code}"
