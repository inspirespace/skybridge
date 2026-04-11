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


def test_credential_store_delete_all_for_job(monkeypatch):
    store = store_mod.CredentialStore()
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    token_job1 = store.issue("job1", "import", {"user": "pilot"}, ttl_seconds=10)
    token_job2 = store.issue("job2", "import", {"user": "other"}, ttl_seconds=10)
    store.store_job_credentials("job1", {"user": "pilot"}, ttl_seconds=10)

    store.delete_all_for_job("job1")

    assert store.claim(token_job1, "job1", "import") is None
    assert store.load_job_credentials("job1") is None
    assert store.claim(token_job2, "job2", "import") == {"user": "other"}


def test_build_credential_store(monkeypatch):
    seen = {}

    class DummyFirestoreCredentialStore:
        def __init__(self, collection: str, project_id: str | None = None) -> None:
            seen["collection"] = collection
            seen["project_id"] = project_id

    monkeypatch.setenv("FIRESTORE_CREDENTIALS_COLLECTION", "custom-credentials")
    monkeypatch.setattr(store_mod, "FirestoreCredentialStore", DummyFirestoreCredentialStore)
    monkeypatch.setattr(store_mod, "resolve_project_id", lambda: "demo-project")

    store = store_mod.build_credential_store()

    assert isinstance(store, DummyFirestoreCredentialStore)
    assert seen == {
        "collection": "custom-credentials",
        "project_id": "demo-project",
    }
