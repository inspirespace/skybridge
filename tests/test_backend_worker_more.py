"""tests/test_backend_worker_more.py module."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

import src.backend.worker as worker
from src.backend.models import JobRecord


class DummyStore:
    def __init__(self, job: JobRecord, token: str | None = None):
        self.job = job
        self.token = token
        self.saved = []
        self.cleared = []

    def load_job(self, _job_id: UUID):
        return self.job

    def read_token(self, _job_id: UUID, _purpose: str):
        return self.token

    def save_job(self, job: JobRecord):
        self.saved.append(job)

    def clear_token(self, job_id: UUID, purpose: str):
        self.cleared.append((job_id, purpose))


class DummyService:
    def __init__(self):
        self.generated = []
        self.accepted = []

    def generate_review(self, job_id, payload):
        self.generated.append((job_id, payload))

    def accept_review(self, job_id, payload):
        self.accepted.append((job_id, payload))


@pytest.fixture
def job_record() -> JobRecord:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return JobRecord(
        job_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        user_id="user-1",
        status="review_queued",
        created_at=now,
        updated_at=now,
    )


def test_env_helpers(monkeypatch):
    monkeypatch.delenv("BACKEND_API_URL", raising=False)
    assert worker._api_url() == "http://api:8000"
    monkeypatch.setenv("BACKEND_API_URL", "http://example.com/")
    assert worker._api_url() == "http://example.com"

    monkeypatch.setenv("BACKEND_WORKER_TOKEN", "tok")
    assert worker._worker_token() == "tok"

    monkeypatch.setenv("BACKEND_SQS_ENABLED", "true")
    assert worker._use_queue() is True
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "false")
    assert worker._use_queue() is False


def test_dynamo_jobs_table(monkeypatch):
    monkeypatch.setenv("BACKEND_DYNAMO_ENABLED", "false")
    assert worker._dynamo_jobs_table() is None

    monkeypatch.setenv("BACKEND_DYNAMO_ENABLED", "true")
    monkeypatch.delenv("DYNAMO_JOBS_TABLE", raising=False)
    with pytest.raises(RuntimeError):
        worker._dynamo_jobs_table()

    monkeypatch.setenv("DYNAMO_JOBS_TABLE", "jobs")
    assert worker._dynamo_jobs_table() == "jobs"


def test_claim_credentials(monkeypatch):
    class DummyResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload or {}

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError("bad")

        def json(self):
            return self._payload

    monkeypatch.setattr(worker, "_worker_token", lambda: "tok")
    monkeypatch.setattr(worker, "_api_url", lambda: "http://api")

    monkeypatch.setattr(worker.requests, "post", lambda *_a, **_k: DummyResponse(503))
    creds, retry = worker._claim_credentials(UUID(int=0), "review", "t")
    assert creds is None and retry is True

    monkeypatch.setattr(worker.requests, "post", lambda *_a, **_k: DummyResponse(410))
    creds, retry = worker._claim_credentials(UUID(int=0), "review", "t")
    assert creds is None and retry is False

    monkeypatch.setattr(worker.requests, "post", lambda *_a, **_k: DummyResponse(200, {"credentials": {"a": 1}}))
    creds, retry = worker._claim_credentials(UUID(int=0), "review", "t")
    assert creds == {"a": 1} and retry is False


def test_handle_job_missing_token(job_record, monkeypatch):
    store = DummyStore(job_record, token=None)
    worker._handle_job(store, job_record.job_id, "review", None)
    assert store.saved
    assert store.saved[-1].status == "failed"


def test_handle_job_retry(job_record, monkeypatch):
    store = DummyStore(job_record, token="tok")
    monkeypatch.setattr(worker, "_claim_credentials", lambda *_a, **_k: (None, True))
    worker._handle_job(store, job_record.job_id, "review", None)
    assert not store.cleared


def test_handle_job_expired_creds(job_record, monkeypatch):
    store = DummyStore(job_record, token="tok")
    monkeypatch.setattr(worker, "_claim_credentials", lambda *_a, **_k: (None, False))
    worker._handle_job(store, job_record.job_id, "review", None)
    assert store.saved[-1].status == "failed"
    assert "expired" in store.saved[-1].error_message


def test_handle_job_review_and_import(job_record, monkeypatch):
    store = DummyStore(job_record, token="tok")
    service = DummyService()
    monkeypatch.setattr(worker, "_claim_credentials", lambda *_a, **_k: ({"cloudahoy_username": "u", "cloudahoy_password": "p", "flysto_username": "f", "flysto_password": "q"}, False))
    monkeypatch.setattr(worker, "JobService", lambda _store: service)

    worker._handle_job(store, job_record.job_id, "review", None)
    assert service.generated

    worker._handle_job(store, job_record.job_id, "import", None)
    assert service.accepted
