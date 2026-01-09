"""tests/test_backend_credential_store.py module."""
from __future__ import annotations

import json
import time

import pytest

import src.backend.credential_store as store_mod


class FakeTable:
    def __init__(self):
        self.items = {}
        self.deleted = []

    def put_item(self, Item):
        self.items[Item["token"]] = Item

    def get_item(self, Key):
        item = self.items.get(Key["token"])
        return {"Item": item} if item else {}

    def delete_item(self, Key):
        self.deleted.append(Key["token"])
        self.items.pop(Key["token"], None)


class FakeResource:
    def __init__(self, table):
        self._table = table

    def Table(self, _name):
        return self._table


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


def test_dynamo_credential_store_issue_and_claim(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(store_mod.boto3, "resource", lambda *_args, **_kwargs: FakeResource(table))
    store = store_mod.DynamoCredentialStore("creds")

    monkeypatch.setattr(time, "time", lambda: 1000.0)
    token = store.issue("job1", "import", {"user": "pilot"}, ttl_seconds=10)
    assert token in table.items

    monkeypatch.setattr(time, "time", lambda: 1001.0)
    assert store.claim(token, "job1", "import") == {"user": "pilot"}
    assert token in table.deleted


def test_dynamo_credential_store_invalid_json(monkeypatch):
    table = FakeTable()
    monkeypatch.setattr(store_mod.boto3, "resource", lambda *_args, **_kwargs: FakeResource(table))
    store = store_mod.DynamoCredentialStore("creds")
    table.items["tok"] = {
        "token": "tok",
        "job_id": "job",
        "purpose": "import",
        "credentials": "not-json",
        "ttl_epoch": 9999,
        "used": False,
    }
    monkeypatch.setattr(time, "time", lambda: 1000.0)
    assert store.claim("tok", "job", "import") is None


def test_build_credential_store(monkeypatch):
    monkeypatch.setenv("BACKEND_DYNAMO_ENABLED", "false")
    store = store_mod.build_credential_store()
    assert isinstance(store, store_mod.CredentialStore)

    monkeypatch.setenv("BACKEND_DYNAMO_ENABLED", "true")
    monkeypatch.delenv("DYNAMO_CREDENTIALS_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        store_mod.build_credential_store()

    monkeypatch.setenv("DYNAMO_CREDENTIALS_TABLE", "creds")
    monkeypatch.setattr(store_mod.boto3, "resource", lambda *_args, **_kwargs: FakeResource(FakeTable()))
    store = store_mod.build_credential_store()
    assert isinstance(store, store_mod.DynamoCredentialStore)
