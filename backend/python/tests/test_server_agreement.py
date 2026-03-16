"""Tests for /api/agreement endpoints."""

from __future__ import annotations


def test_agreement_not_accepted_for_new_user(client, auth_headers):
    resp = client.get("/api/agreement", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["accepted"] is False
    assert data["accepted_at"] is None


def test_accept_agreement(client, auth_headers):
    resp = client.post("/api/agreement", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "accepted"


def test_agreement_accepted_after_post(client, auth_headers):
    client.post("/api/agreement", headers=auth_headers)
    resp = client.get("/api/agreement", headers=auth_headers)
    data = resp.json()
    assert data["accepted"] is True
    assert data["accepted_at"] is not None
