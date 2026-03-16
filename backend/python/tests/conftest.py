"""Shared test fixtures for the TokReducer API test suite.

Patches Firebase Admin SDK *before* server.py is imported so module-level
initialization (firebase_admin.initialize_app, firestore.client) never hits
the network.
"""

from __future__ import annotations

import copy
import os
import sys
from collections import defaultdict
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ""

TEST_UID = "test-user-123"
TEST_EMAIL = "test@example.com"


# ── In-memory Firestore fakes ────────────────────────────────────────────


class _Increment:
    """Stand-in for firestore.Increment."""
    def __init__(self, amount: int):
        self.amount = amount


class _FakeDocSnapshot:
    def __init__(self, data: dict[str, Any] | None, doc_id: str = "doc"):
        self._data = data
        self._id = doc_id
        self.exists = data is not None
        self.reference: Any = None

    @property
    def id(self):
        return self._id

    def to_dict(self) -> dict[str, Any] | None:
        return copy.deepcopy(self._data) if self._data else None


class _FakeDocRef:
    def __init__(self, store: dict[str, Any], path: str):
        self._store = store
        self._path = path

    @property
    def reference(self):
        return self

    def get(self) -> _FakeDocSnapshot:
        data = self._store.get(self._path)
        doc_id = self._path.rsplit("/", 1)[-1]
        snap = _FakeDocSnapshot(data, doc_id)
        snap.reference = self
        return snap

    def set(self, data: dict[str, Any]) -> None:
        self._store[self._path] = copy.deepcopy(data)

    def update(self, data: dict[str, Any]) -> None:
        existing = self._store.get(self._path, {})
        for k, v in data.items():
            if isinstance(v, _Increment):
                existing[k] = existing.get(k, 0) + v.amount
            else:
                existing[k] = v
        self._store[self._path] = existing

    def collection(self, name: str) -> "_FakeCollectionRef":
        return _FakeCollectionRef(self._store, f"{self._path}/{name}")


class _FakeCollectionRef:
    _counters: dict[str, int] = defaultdict(int)

    def __init__(self, store: dict[str, Any], path: str):
        self._store = store
        self._path = path

    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(self._store, f"{self._path}/{doc_id}")

    def add(self, data: dict[str, Any]) -> tuple[None, _FakeDocRef]:
        _FakeCollectionRef._counters[self._path] += 1
        doc_id = f"auto_{_FakeCollectionRef._counters[self._path]}"
        ref = _FakeDocRef(self._store, f"{self._path}/{doc_id}")
        ref.set(data)
        return None, ref

    def order_by(self, field: str, direction: Any = None) -> "_FakeQuery":
        docs = []
        prefix = self._path + "/"
        depth = prefix.count("/")
        for key, val in list(self._store.items()):
            if key.startswith(prefix) and key.count("/") == depth:
                doc_id = key.rsplit("/", 1)[-1]
                snap = _FakeDocSnapshot(val, doc_id)
                snap.reference = _FakeDocRef(self._store, key)
                docs.append(snap)
        docs.sort(key=lambda d: (d.to_dict() or {}).get(field, ""), reverse=True)
        return _FakeQuery(docs)

    def where(self, field: str, op: str, value: Any) -> "_FakeQuery":
        docs = []
        prefix = self._path + "/"
        depth = prefix.count("/")
        for key, val in list(self._store.items()):
            if key.startswith(prefix) and key.count("/") == depth:
                if val.get(field) == value:
                    doc_id = key.rsplit("/", 1)[-1]
                    snap = _FakeDocSnapshot(val, doc_id)
                    snap.reference = _FakeDocRef(self._store, key)
                    docs.append(snap)
        return _FakeQuery(docs)


class _FakeQuery:
    def __init__(self, docs: list[_FakeDocSnapshot]):
        self._docs = docs

    def limit(self, n: int) -> "_FakeQuery":
        return _FakeQuery(self._docs[:n])

    def stream(self):
        return iter(self._docs)


class _FakeFirestoreClient:
    def __init__(self, store: dict[str, Any] | None = None):
        self._store: dict[str, Any] = store if store is not None else {}

    def collection(self, name: str) -> _FakeCollectionRef:
        return _FakeCollectionRef(self._store, name)


# ── Module-level patching ────────────────────────────────────────────────

_mock_fb_auth = MagicMock()
_mock_fb_auth.verify_id_token.return_value = {"uid": TEST_UID, "email": TEST_EMAIL}

_mock_firestore_module = MagicMock()
_mock_firestore_module.Query.DESCENDING = "DESCENDING"
_mock_firestore_module.Increment = lambda n: _Increment(n)

_mock_firebase_admin = MagicMock()
_mock_firebase_admin._apps = {"default": True}

sys.modules.setdefault("firebase_admin", _mock_firebase_admin)
sys.modules.setdefault("firebase_admin.auth", _mock_fb_auth)
sys.modules.setdefault("firebase_admin.credentials", MagicMock())
sys.modules.setdefault("firebase_admin.firestore", _mock_firestore_module)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset auto-ID counters and rate limiter between tests."""
    _FakeCollectionRef._counters.clear()
    yield
    try:
        from tokreducer.api.server import _rate_buckets
        _rate_buckets.clear()
    except Exception:
        pass


@pytest.fixture()
def firestore_store():
    """Raw dict backing the fake Firestore — inspect it in tests."""
    return {}


@pytest.fixture()
def _patch_firebase(firestore_store):
    """Swap the server's _db with a fresh in-memory store for each test."""
    import tokreducer.api.server as srv

    fake_db = _FakeFirestoreClient(firestore_store)
    old_db = srv._db

    srv._db = fake_db
    srv.fb_auth = _mock_fb_auth
    srv.firestore = _mock_firestore_module
    srv.firebase_admin = _mock_firebase_admin

    _mock_fb_auth.verify_id_token.reset_mock()
    _mock_fb_auth.verify_id_token.return_value = {"uid": TEST_UID, "email": TEST_EMAIL}
    _mock_fb_auth.verify_id_token.side_effect = None

    yield {
        "admin": _mock_firebase_admin,
        "auth": _mock_fb_auth,
        "firestore_module": _mock_firestore_module,
        "db": fake_db,
        "store": firestore_store,
    }

    srv._db = old_db


@pytest.fixture()
def client(_patch_firebase):
    """FastAPI TestClient with mocked Firebase."""
    from starlette.testclient import TestClient
    from tokreducer.api.server import app
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def auth_headers():
    return {"Authorization": "Bearer mock-token"}


@pytest.fixture()
def mocks(_patch_firebase):
    """Expose the mock objects for assertions."""
    return _patch_firebase
