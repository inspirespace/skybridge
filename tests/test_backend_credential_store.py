"""tests/test_backend_credential_store.py module."""
from __future__ import annotations

import time

import src.backend.credential_store as store_mod


def test_credential_store_issue_and_claim(monkeypatch):
    store = store_mod.CredentialStore()
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    token = store.issue("job1", "import", {"user": "pilot"}, ttl_seconds=10)
    assert store.claim(token, "job1", "import") == {"user": "pilot"}
    assert store.claim(token, "job1", "import") is None


def test_credential_store_rejects_wrong_job(monkeypatch):
    store = store_mod.CredentialStore()
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    token = store.issue("job1", "import", {"user": "pilot"}, ttl_seconds=10)
    assert store.claim(token, "job2", "import") is None


def test_credential_store_expires(monkeypatch):
    store = store_mod.CredentialStore()
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    token = store.issue("job1", "import", {"user": "pilot"}, ttl_seconds=1)
    monkeypatch.setattr(time, "time", lambda: 1002.0)
    assert store.claim(token, "job1", "import") is None


def test_build_credential_store(monkeypatch):
    monkeypatch.setenv("BACKEND_FIRESTORE_ENABLED", "false")
    store = store_mod.build_credential_store()
    assert isinstance(store, store_mod.CredentialStore)
