"""Tests for Firebase Storage object-store resolution."""
from __future__ import annotations

from pathlib import Path

import src.backend.env as env_mod
import src.backend.object_store as object_store_mod


def test_resolve_storage_bucket_from_firebase_config(monkeypatch):
    env_mod.resolve_storage_bucket.cache_clear()
    env_mod._read_firebase_config.cache_clear()
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.delenv("FIREBASE_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("FIREBASE_PROJECT_ID", raising=False)
    monkeypatch.setenv("FIREBASE_CONFIG", '{"storageBucket":"runtime-bucket.firebasestorage.app"}')

    assert env_mod.resolve_storage_bucket() == "runtime-bucket.firebasestorage.app"

    env_mod.resolve_storage_bucket.cache_clear()
    env_mod._read_firebase_config.cache_clear()


def test_resolve_storage_bucket_defaults_from_project_id(monkeypatch):
    env_mod.resolve_storage_bucket.cache_clear()
    env_mod._read_firebase_config.cache_clear()
    monkeypatch.delenv("GCS_BUCKET", raising=False)
    monkeypatch.delenv("FIREBASE_STORAGE_BUCKET", raising=False)
    monkeypatch.delenv("FIREBASE_CONFIG", raising=False)
    monkeypatch.setattr(env_mod, "resolve_project_id", lambda: "demo-project")

    assert env_mod.resolve_storage_bucket() == "demo-project.firebasestorage.app"

    env_mod.resolve_storage_bucket.cache_clear()
    env_mod._read_firebase_config.cache_clear()


def test_build_object_store_uses_resolved_bucket(monkeypatch):
    seen = {}

    class DummyGcsObjectStore:
        def __init__(self, *, bucket: str, prefix: str, project_id: str | None) -> None:
            seen["bucket"] = bucket
            seen["prefix"] = prefix
            seen["project_id"] = project_id

    monkeypatch.setattr(object_store_mod, "GcsObjectStore", DummyGcsObjectStore)
    monkeypatch.setattr(object_store_mod, "resolve_storage_bucket", lambda: "runtime-bucket.firebasestorage.app")
    monkeypatch.setattr(object_store_mod, "resolve_project_id", lambda: "demo-project")
    monkeypatch.setenv("GCS_PREFIX", "jobs")

    store = object_store_mod.build_object_store_from_env()

    assert isinstance(store, DummyGcsObjectStore)
    assert seen == {
        "bucket": "runtime-bucket.firebasestorage.app",
        "prefix": "jobs",
        "project_id": "demo-project",
    }
