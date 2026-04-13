"""More JobStore coverage for local/object-store paths."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json

import pytest

import src.backend.credential_store as credential_store_mod
from src.backend.models import JobRecord
import src.backend.store as store_mod
from src.backend.store import JobStore


class FakeObjectStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.json_calls: list[str] = []
        self.files: dict[str, dict] = {}
        self.bytes_payloads: dict[str, bytes] = {}
        self.raise_on_put = False
        self.raise_on_get = False

    def key_for(self, *parts: str) -> str:
        return "/".join(parts)

    def delete_prefix(self, prefix: str) -> None:
        self.deleted.append(prefix)

    def put_json(self, key: str, payload: dict) -> None:
        if self.raise_on_put:
            raise RuntimeError("boom")
        self.json_calls.append(key)
        self.files[key] = payload

    def put_file(self, key: str, _path: Path) -> None:
        self.json_calls.append(key)

    def list_prefix(self, prefix: str) -> list[str]:
        keys = set(self.files)
        keys.update(self.bytes_payloads)
        if not prefix:
            return sorted(keys)
        return sorted(
            key[len(prefix) + 1 :] if key.startswith(f"{prefix}/") else key
            for key in keys
            if key == prefix or key.startswith(f"{prefix}/")
        )

    def get_json(self, key: str):
        if self.raise_on_get:
            raise RuntimeError("boom")
        return self.files.get(key)

    def get_bytes(self, key: str):
        return self.bytes_payloads.get(key)

    def download_to_file(self, key: str, file_obj) -> bool:
        payload = self.bytes_payloads.get(key)
        if payload is None:
            return False
        file_obj.write(payload)
        return True


class _FakeDocSnapshot:
    def __init__(self, doc_id: str, payload: dict) -> None:
        self.id = doc_id
        self._payload = payload
        self.exists = True
        self.reference = self
        self.deleted = False

    def to_dict(self) -> dict:
        return self._payload

    def get(self):
        return self

    def delete(self) -> None:
        self.deleted = True


class _FakeCollection:
    def __init__(self, snapshot: _FakeDocSnapshot) -> None:
        self._snapshot = snapshot

    def where(self, *_args, **_kwargs):
        return self

    def stream(self):
        return [self._snapshot]

    def document(self, _doc_id: str):
        return self._snapshot


def _job(store: JobStore, user_id: str = "user-1") -> JobRecord:
    now = datetime.now(timezone.utc)
    job = JobRecord(
        job_id=uuid4(),
        user_id=user_id,
        status="review_ready",
        created_at=now,
        updated_at=now,
    )
    store.save_job(job)
    return job


def test_object_prefix_for_missing_job(tmp_path: Path):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    assert store._object_prefix_for_job(uuid4()) == ""


def test_delete_job_deletes_remote_prefix_by_default(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    job = _job(store)
    monkeypatch.delenv("BACKEND_OBJECT_STORE_DELETE_ON_CLEAR", raising=False)

    store.delete_job(job.job_id, user_id=job.user_id)
    assert store.object_store.deleted == [store.object_store.key_for(job.user_id, str(job.job_id))]


def test_delete_job_can_skip_remote_prefix_deletion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    job = _job(store)
    monkeypatch.setenv("BACKEND_OBJECT_STORE_DELETE_ON_CLEAR", "0")

    store.delete_job(job.job_id, user_id=job.user_id)

    assert store.object_store.deleted == []


def test_delete_job_cleans_credentials_when_encryption_key_is_configured(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    store = JobStore(tmp_path)
    job = _job(store)
    seen = {}

    class _DummyCredentialStore:
        def delete_all_for_job(self, job_id: str) -> None:
            seen["job_id"] = job_id

    monkeypatch.setenv("BACKEND_ENCRYPTION_KEY", "x" * 32)
    monkeypatch.setattr(credential_store_mod, "build_credential_store", lambda: _DummyCredentialStore())

    store.delete_job(job.job_id, user_id=job.user_id)

    assert seen["job_id"] == str(job.job_id)


def test_write_artifact_uploads_and_ignores_object_store_errors(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store)

    object_store.raise_on_put = True
    store.write_artifact(job.job_id, "summary.json", {"ok": True})

    object_store.raise_on_put = False
    store.write_artifact(job.job_id, "summary.json", {"ok": True})
    assert object_store.json_calls


def test_list_and_load_artifacts_local(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job(store)

    artifact = store.job_dir(job.job_id) / "artifact.json"
    artifact.write_text(json.dumps({"ok": True}))

    artifacts = store.list_artifacts(job.job_id)
    assert "artifact.json" in artifacts
    payload = store.load_artifact(job.job_id, "artifact.json")
    assert payload == {"ok": True}


def test_list_jobs_filters_user(tmp_path: Path):
    store = JobStore(tmp_path)
    job1 = _job(store, user_id="user-1")
    _job(store, user_id="user-2")

    jobs = store.list_jobs("user-1")
    assert len(jobs) == 1
    assert jobs[0].job_id == job1.job_id


def test_materialize_artifact_file_from_object_store(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store)
    target = store.job_dir(job.job_id) / "migration.db"
    key = object_store.key_for(job.user_id, str(job.job_id), "migration.db")
    object_store.bytes_payloads[key] = b"sqlite-bytes"

    restored = store.materialize_artifact_file(job.job_id, "migration.db", target)

    assert restored is True
    assert target.read_bytes() == b"sqlite-bytes"


def test_materialize_artifact_file_prefers_remote_over_stale_local(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store)
    target = store.job_dir(job.job_id) / "migration.db"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"stale-local")
    key = object_store.key_for(job.user_id, str(job.job_id), "migration.db")
    object_store.bytes_payloads[key] = b"remote-fresh"

    restored = store.materialize_artifact_file(job.job_id, "migration.db", target)

    assert restored is True
    assert target.read_bytes() == b"remote-fresh"


def test_load_artifact_prefers_remote_over_stale_local(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store)
    artifact = store.job_dir(job.job_id) / "artifact.json"
    artifact.write_text(json.dumps({"source": "local"}))
    key = object_store.key_for(job.user_id, str(job.job_id), "artifact.json")
    object_store.put_json(key, {"source": "remote"})

    payload = store.load_artifact(job.job_id, "artifact.json")

    assert payload == {"source": "remote"}
    assert json.loads(artifact.read_text()) == {"source": "remote"}


def test_load_artifact_falls_back_to_local_when_remote_read_fails(tmp_path: Path):
    object_store = FakeObjectStore()
    object_store.raise_on_get = True
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store)
    artifact = store.job_dir(job.job_id) / "artifact.json"
    artifact.write_text(json.dumps({"source": "local"}))

    payload = store.load_artifact(job.job_id, "artifact.json")

    assert payload == {"source": "local"}


def test_load_job_expired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)
    job = job.model_copy(update={"created_at": datetime.now(timezone.utc) - timedelta(days=10)})
    store.save_job(job)
    monkeypatch.setenv("BACKEND_RETENTION_DAYS", "1")

    with pytest.raises(FileNotFoundError):
        store.load_job(job.job_id)


def test_cleanup_expired_firestore_uses_delete_job_without_recursive_load(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    store = JobStore(tmp_path)
    snapshot = _FakeDocSnapshot(
        str(uuid4()),
        {
            "user_id": "user-1",
            "ttl_epoch": 1,
        },
    )
    store._firestore_collection = _FakeCollection(snapshot)

    deleted = store.cleanup_expired()

    assert deleted == 1
    assert snapshot.deleted is True


def test_cleanup_expired_sweeps_orphaned_remote_prefixes(tmp_path: Path):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job(store, user_id="user-1")
    active_key = object_store.key_for(job.user_id, str(job.job_id), "review.json")
    orphan_job_id = str(uuid4())
    orphan_key = object_store.key_for("user-1", orphan_job_id, "review.json")
    object_store.put_json(active_key, {"ok": True})
    object_store.put_json(orphan_key, {"ok": False})

    deleted = store.cleanup_expired()

    assert deleted == 0
    assert object_store.deleted == [object_store.key_for("user-1", orphan_job_id)]
