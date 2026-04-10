"""More JobStore coverage for local/object-store paths."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json

import pytest

from src.backend.models import JobRecord
from src.backend.store import JobStore


class FakeObjectStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []
        self.json_calls: list[str] = []
        self.files: dict[str, dict] = {}
        self.bytes_payloads: dict[str, bytes] = {}
        self.raise_on_put = False

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

    def list_prefix(self, _prefix: str) -> list[str]:
        return ["review.json"]

    def get_json(self, key: str):
        return self.files.get(key)

    def get_bytes(self, key: str):
        return self.bytes_payloads.get(key)


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


def test_delete_job_deletes_remote_prefix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path, object_store=FakeObjectStore())
    job = _job(store)
    monkeypatch.setenv("BACKEND_OBJECT_STORE_DELETE_ON_CLEAR", "1")

    store.delete_job(job.job_id, user_id=job.user_id)
    assert store.object_store.deleted


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


def test_load_job_expired(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)
    job = job.model_copy(update={"created_at": datetime.now(timezone.utc) - timedelta(days=10)})
    store.save_job(job)
    monkeypatch.setenv("BACKEND_RETENTION_DAYS", "1")

    with pytest.raises(FileNotFoundError):
        store.load_job(job.job_id)
