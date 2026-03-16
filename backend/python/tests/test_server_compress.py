"""Tests for /compress and /decompress endpoints."""

from __future__ import annotations


def test_compress_returns_compressed_text(client, auth_headers):
    resp = client.post(
        "/compress",
        json={"prompt": "Please help me understand the concept of machine learning", "level": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "compressed" in data
    assert data["original_tokens"] >= 0
    assert data["compressed_tokens"] >= 0
    assert isinstance(data["reduction_pct"], (int, float))


def test_compress_level_0_passthrough(client, auth_headers):
    prompt = "Hello world"
    resp = client.post("/compress", json={"prompt": prompt, "level": 0}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["compressed"] == prompt


def test_compress_invalid_level_returns_422(client, auth_headers):
    resp = client.post("/compress", json={"prompt": "test", "level": 5}, headers=auth_headers)
    assert resp.status_code == 422


def test_compress_negative_level_returns_422(client, auth_headers):
    resp = client.post("/compress", json={"prompt": "test", "level": -1}, headers=auth_headers)
    assert resp.status_code == 422


def test_decompress_returns_text(client, auth_headers):
    resp = client.post("/decompress", json={"text": "hlp undrstnd ML"}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "decompressed" in data
    assert isinstance(data["decompressed"], str)


def test_compress_empty_prompt(client, auth_headers):
    resp = client.post("/compress", json={"prompt": "", "level": 2}, headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data["compressed"], str)
