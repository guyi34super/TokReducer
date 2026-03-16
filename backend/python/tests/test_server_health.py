"""Tests for public endpoints and unauthenticated access."""

from __future__ import annotations


def test_health_returns_200(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_health_contains_version(client):
    data = client.get("/health").json()
    assert data["version"] == "1.0.0"


def test_compress_requires_auth(client):
    resp = client.post("/compress", json={"prompt": "hello", "level": 2})
    assert resp.status_code == 401


def test_config_requires_auth(client):
    resp = client.get("/api/config")
    assert resp.status_code == 401


def test_logs_requires_auth(client):
    resp = client.get("/api/logs")
    assert resp.status_code == 401


def test_usage_requires_auth(client):
    resp = client.get("/api/usage")
    assert resp.status_code == 401


def test_agreement_requires_auth(client):
    resp = client.get("/api/agreement")
    assert resp.status_code == 401


def test_subscription_requires_auth(client):
    resp = client.get("/api/subscription")
    assert resp.status_code == 401


def test_audit_logs_requires_auth(client):
    resp = client.get("/api/audit-logs")
    assert resp.status_code == 401
