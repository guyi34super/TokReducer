"""Tests for /api/logs and /api/audit-logs endpoints."""

from __future__ import annotations

from tests.conftest import TEST_UID


def test_logs_empty_for_new_user(client, auth_headers):
    resp = client.get("/api/logs", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["entries"] == []
    assert data["summary"]["total_requests"] == 0


def test_logs_summary_calculation(client, auth_headers, firestore_store):
    base = f"users/{TEST_UID}/logs"
    firestore_store[f"{base}/log1"] = {
        "timestamp": "2025-01-01T00:00:00",
        "model": "gpt-4o",
        "original_tokens": 100,
        "compressed_tokens": 60,
        "reduction_pct": 40.0,
        "output_tokens": 50,
        "latency_ms": 200,
        "status": "ok",
        "ip": "1.2.3.4",
        "user_agent": "test",
        "endpoint": "/v1/chat/completions",
    }
    firestore_store[f"{base}/log2"] = {
        "timestamp": "2025-01-01T00:01:00",
        "model": "gpt-4o",
        "original_tokens": 200,
        "compressed_tokens": 100,
        "reduction_pct": 50.0,
        "output_tokens": 80,
        "latency_ms": 300,
        "status": "ok",
        "ip": "5.6.7.8",
        "user_agent": "test2",
        "endpoint": "/v1/chat/completions",
    }

    resp = client.get("/api/logs", headers=auth_headers)
    data = resp.json()
    assert data["summary"]["total_requests"] == 2
    assert data["summary"]["total_tokens_saved"] == 140
    assert data["summary"]["avg_reduction_pct"] == 45.0


def test_audit_logs_empty_initially(client, auth_headers):
    resp = client.get("/api/audit-logs", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["entries"] == []


def test_audit_logs_populated_after_action(client, auth_headers):
    client.get("/api/config", headers=auth_headers)
    resp = client.get("/api/audit-logs", headers=auth_headers)
    entries = resp.json()["entries"]
    actions = [e["action"] for e in entries]
    assert "config.view" in actions
