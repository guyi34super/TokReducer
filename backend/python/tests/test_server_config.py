"""Tests for /api/config endpoints (multiple configs + selected)."""

from __future__ import annotations


def test_get_config_returns_empty_list_when_no_configs(client, auth_headers):
    resp = client.get("/api/config", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "configs" in data
    assert "selected_id" in data
    assert data["configs"] == []
    assert data["selected_id"] is None


def test_post_config_creates_and_returns_list(client, auth_headers):
    payload = {
        "name": "Test",
        "provider": "anthropic",
        "api_key": "sk-test-12345678",
        "model": "claude-3",
        "level": 1,
        "upstream_url": "https://api.anthropic.com",
    }
    resp = client.post("/api/config", json=payload, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "saved"
    assert len(body["configs"]) == 1
    assert body["selected_id"] is not None
    assert body["configs"][0]["provider"] == "anthropic"
    assert body["configs"][0]["model"] == "claude-3"
    assert body["configs"][0]["level"] == 1

    resp2 = client.get("/api/config", headers=auth_headers)
    data = resp2.json()
    assert len(data["configs"]) == 1
    assert data["configs"][0]["provider"] == "anthropic"
    assert data["selected_id"] == data["configs"][0]["id"]


def test_api_key_is_masked_in_get(client, auth_headers):
    payload = {
        "name": "Key1",
        "provider": "openai",
        "api_key": "sk-abcdefghijklmnop",
        "model": "gpt-4o",
        "level": 2,
        "upstream_url": "https://api.openai.com",
    }
    client.post("/api/config", json=payload, headers=auth_headers)
    resp = client.get("/api/config", headers=auth_headers)
    configs = resp.json()["configs"]
    assert len(configs) == 1
    key = configs[0]["api_key"]
    assert "..." in key
    assert key.startswith("sk-a")
    assert key.endswith("mnop")


def test_masked_key_preserves_real_key_on_update(client, auth_headers):
    real_key = "sk-abcdefghijklmnop"
    create = client.post(
        "/api/config",
        json={
            "name": "Key1",
            "provider": "openai",
            "api_key": real_key,
            "model": "gpt-4o",
            "level": 2,
            "upstream_url": "https://api.openai.com",
        },
        headers=auth_headers,
    )
    cid = create.json()["configs"][0]["id"]
    masked = create.json()["configs"][0]["api_key"]

    client.post(
        "/api/config",
        json={
            "id": cid,
            "name": "Key1",
            "provider": "openai",
            "api_key": masked,
            "model": "gpt-4o",
            "level": 2,
            "upstream_url": "https://api.openai.com",
        },
        headers=auth_headers,
    )

    resp = client.get("/api/config", headers=auth_headers)
    key = resp.json()["configs"][0]["api_key"]
    assert key.startswith("sk-a")
    assert key.endswith("mnop")


def test_set_selected_and_delete(client, auth_headers):
    r1 = client.post(
        "/api/config",
        json={"name": "A", "api_key": "sk-a", "provider": "openai", "level": 0, "upstream_url": "https://api.openai.com"},
        headers=auth_headers,
    )
    r2 = client.post(
        "/api/config",
        json={"name": "B", "api_key": "sk-b", "provider": "openai", "level": 1, "upstream_url": "https://api.openai.com"},
        headers=auth_headers,
    )
    id_a = r1.json()["configs"][0]["id"]
    id_b = r2.json()["configs"][1]["id"]

    client.post("/api/config/selected", json={"selected_id": id_b}, headers=auth_headers)
    get_resp = client.get("/api/config", headers=auth_headers)
    assert get_resp.json()["selected_id"] == id_b

    del_resp = client.delete(f"/api/config/{id_b}", headers=auth_headers)
    assert del_resp.json()["status"] == "deleted"
    assert len(del_resp.json()["configs"]) == 1
    assert del_resp.json()["selected_id"] == id_a
