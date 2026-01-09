"""Extra JobStore coverage for edge branches."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import json

import pytest

from src.backend.models import JobRecord
from src.backend.store import JobStore


class ErrorObjectStore:
    def key_for(self, *parts: str) -> str:
        return "/".join(parts)

    def delete_prefix(self, _prefix: str) -> None:
        raise RuntimeError("boom")

    def put_file(self, _key: str, _path: Path) -> None:
        raise RuntimeError("boom")

    def put_json(self, _key: str, _payload: dict) -> None:
        raise RuntimeError("boom")

    def list_prefix(self, _prefix: str) -> list[str]:
        return []

    def get_json(self, _key: str):
        return None


def _job(store: JobStore) -> JobRecord:
    now = datetime.now(timezone.utc)
    job = JobRecord(
        job_id=uuid4(),
        user_id="user-1",
        status="review_ready",
        created_at=now,
        updated_at=now,
    )
    store.save_job(job)
    return job


def test_object_prefix_without_store(tmp_path: Path):
    store = JobStore(tmp_path)
    assert store._object_prefix_for_job(uuid4()) == ""


def test_delete_job_handles_object_store_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path, object_store=ErrorObjectStore())
    job = _job(store)
    monkeypatch.setenv("BACKEND_S3_DELETE_ON_CLEAR", "1")
    store.delete_job(job.job_id, user_id=job.user_id)


def test_upload_artifact_handles_errors(tmp_path: Path):
    store = JobStore(tmp_path, object_store=ErrorObjectStore())
    job = _job(store)
    data_file = tmp_path / "file.txt"
    data_file.write_text("data")
    store.upload_artifact(job.job_id, "file.txt", data_file)


def test_write_artifact_handles_errors(tmp_path: Path):
    store = JobStore(tmp_path, object_store=ErrorObjectStore())
    job = _job(store)
    store.write_artifact(job.job_id, "artifact.json", {"ok": True})


def test_load_artifact_missing_raises(tmp_path: Path):
    store = JobStore(tmp_path)
    job = _job(store)
    with pytest.raises(FileNotFoundError):
        store.load_artifact(job.job_id, "missing.json")


def test_list_all_jobs_skips_empty_dirs(tmp_path: Path):
    store = JobStore(tmp_path)
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    jobs = store.list_all_jobs()
    assert jobs == []


def test_delete_jobs_for_user_ignores_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)

    def fake_delete(*_args, **_kwargs):
        raise FileNotFoundError

    monkeypatch.setattr(store, "delete_job", fake_delete)
    store.delete_jobs_for_user(job.user_id)
