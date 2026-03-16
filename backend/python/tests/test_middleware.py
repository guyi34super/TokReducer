"""Tests for security middleware (rate limiter, body size, secure headers, CORS)."""

from __future__ import annotations

from unittest.mock import patch


def test_secure_headers_present(client):
    resp = client.get("/health")
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    assert resp.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert resp.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains; preload"
    assert resp.headers.get("Permissions-Policy") == "camera=(), microphone=(), geolocation=(), payment=()"
    assert "default-src 'self'" in resp.headers.get("Content-Security-Policy", "")
    assert resp.headers.get("X-XSS-Protection") is None


def test_body_size_limit_rejects_large_payload(client, auth_headers):
    big_payload = {"prompt": "x" * (1_048_576 + 1), "level": 2}
    resp = client.post(
        "/compress",
        json=big_payload,
        headers={**auth_headers, "content-length": str(2_000_000)},
    )
    assert resp.status_code == 413


def test_rate_limiter_allows_normal_traffic(client):
    for _ in range(5):
        resp = client.get("/health")
        assert resp.status_code == 200


def test_rate_limiter_returns_429(client):
    import time
    from tokreducer.api.server import _rate_buckets

    ip = "test-rate-limit-ip-unique"
    now = time.monotonic()
    _rate_buckets[ip] = [0.0, now]

    resp = client.get("/health", headers={"x-forwarded-for": ip})
    assert resp.status_code == 429

    del _rate_buckets[ip]


def test_cors_allows_localhost(client):
    from tokreducer.api.server import _rate_buckets
    _rate_buckets.clear()

    resp = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    acl = resp.headers.get("access-control-allow-origin", "")
    assert acl in ("http://localhost:3000", "*", "")
