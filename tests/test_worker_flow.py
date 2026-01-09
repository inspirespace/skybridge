"""Extra coverage tests for backend worker."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import requests

import src.backend.worker as worker
from src.backend.models import JobRecord
from src.backend.store import JobStore


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _job(store: JobStore) -> JobRecord:
    now = datetime.now(timezone.utc)
    job = JobRecord(
        job_id=uuid4(),
        user_id="user-1",
        status="review_queued",
        created_at=now,
        updated_at=now,
    )
    store.save_job(job)
    return job


def test_claim_credentials_status_handling(monkeypatch: pytest.MonkeyPatch):
    def fake_post(url, json=None, headers=None, timeout=None):
        if "retry" in url:
            return DummyResponse(503)
        if "gone" in url:
            return DummyResponse(410)
        return DummyResponse(200, {"credentials": {"cloudahoy_username": "a"}})

    monkeypatch.setattr(worker.requests, "post", fake_post)

    creds, retry = worker._claim_credentials(uuid4(), "review", "token")
    assert creds == {"cloudahoy_username": "a"}
    assert retry is False

    monkeypatch.setattr(worker, "_api_url", lambda: "http://api/retry")
    creds, retry = worker._claim_credentials(uuid4(), "review", "token")
    assert creds is None
    assert retry is True

    monkeypatch.setattr(worker, "_api_url", lambda: "http://api/gone")
    creds, retry = worker._claim_credentials(uuid4(), "review", "token")
    assert creds is None
    assert retry is False


def test_handle_job_missing_token(tmp_path):
    store = JobStore(tmp_path)
    job = _job(store)

    worker._handle_job(store, job.job_id, "review", None)
    updated = store.load_job(job.job_id)
    assert updated.status == "failed"
    assert "Missing review token" in (updated.error_message or "")


def test_handle_job_expired_credentials(tmp_path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)
    store.write_token(job.job_id, "review", "tok")

    monkeypatch.setattr(worker, "_claim_credentials", lambda *_args, **_kwargs: (None, False))

    worker._handle_job(store, job.job_id, "review", None)
    updated = store.load_job(job.job_id)
    assert updated.status == "failed"
    assert "Review credentials expired" in (updated.error_message or "")
    assert store.read_token(job.job_id, "review") is None


def test_handle_job_review_success(tmp_path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)
    store.write_token(job.job_id, "review", "tok")

    monkeypatch.setattr(
        worker,
        "_claim_credentials",
        lambda *_args, **_kwargs: (
            {
                "cloudahoy_username": "a",
                "cloudahoy_password": "b",
                "flysto_username": "c",
                "flysto_password": "d",
            },
            False,
        ),
    )
    called: dict[str, object] = {}

    def fake_generate_review(self, job_id, payload):
        called["job_id"] = job_id
        called["payload"] = payload

    monkeypatch.setattr(worker.JobService, "generate_review", fake_generate_review)

    worker._handle_job(store, job.job_id, "review", None)
    assert called.get("job_id") == job.job_id
    assert store.read_token(job.job_id, "review") is None


def test_handle_job_import_success(tmp_path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    job = _job(store)
    store.write_token(job.job_id, "import", "tok")

    monkeypatch.setattr(
        worker,
        "_claim_credentials",
        lambda *_args, **_kwargs: (
            {
                "cloudahoy_username": "a",
                "cloudahoy_password": "b",
                "flysto_username": "c",
                "flysto_password": "d",
            },
            False,
        ),
    )
    called: dict[str, object] = {}

    def fake_accept_review(self, job_id, payload):
        called["job_id"] = job_id
        called["payload"] = payload

    monkeypatch.setattr(worker.JobService, "accept_review", fake_accept_review)

    worker._handle_job(store, job.job_id, "import", None)
    assert called.get("job_id") == job.job_id
    assert store.read_token(job.job_id, "import") is None


def test_dynamo_jobs_table_requires_name(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BACKEND_DYNAMO_ENABLED", "1")
    monkeypatch.delenv("DYNAMO_JOBS_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        worker._dynamo_jobs_table()


def test_use_queue_parsing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "true")
    assert worker._use_queue() is True
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "false")
    assert worker._use_queue() is False
