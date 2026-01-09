"""Tests for backend worker flow."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.backend.models import JobRecord, JobCreateRequest, JobAcceptRequest
from src.backend.store import JobStore
import src.backend.worker as worker


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


class DummyService:
    def __init__(self, store: JobStore) -> None:
        self.store = store
        self.called: list[tuple[str, str]] = []

    def generate_review(self, job_id, payload):
        self.called.append(("review", str(job_id)))

    def accept_review(self, job_id, payload):
        self.called.append(("import", str(job_id)))


def _job(status: str) -> JobRecord:
    now = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    return JobRecord(
        job_id=uuid4(),
        user_id="pilot",
        status=status,
        created_at=now,
        updated_at=now,
        progress_log=[],
    )


def test_claim_credentials_handles_retry(monkeypatch: pytest.MonkeyPatch) -> None:
    """Claim credentials should request retry on 503."""
    monkeypatch.setattr(worker.requests, "post", lambda *args, **kwargs: DummyResponse(503))
    creds, retry = worker._claim_credentials(uuid4(), "review", "token")
    assert creds is None
    assert retry is True


def test_handle_job_missing_token_marks_failed(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Missing token should fail the job."""
    store = JobStore(tmp_path)
    job = _job("review_queued")
    store.save_job(job)

    monkeypatch.setattr(worker, "_claim_credentials", lambda *args, **kwargs: ({}, False))

    worker._handle_job(store, job.job_id, "review", None)
    updated = store.load_job(job.job_id)
    assert updated.status == "failed"
    assert "Missing" in (updated.error_message or "")


def test_handle_job_expired_creds(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Expired credentials should mark job failed."""
    store = JobStore(tmp_path)
    job = _job("review_queued")
    store.save_job(job)
    store.write_token(job.job_id, "review", "token")

    monkeypatch.setattr(worker, "_claim_credentials", lambda *args, **kwargs: (None, False))

    worker._handle_job(store, job.job_id, "review", None)
    updated = store.load_job(job.job_id)
    assert updated.status == "failed"
    assert "expired" in (updated.error_message or "").lower()


def test_handle_job_dispatches_review(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Handle job should call generate_review when purpose is review."""
    store = JobStore(tmp_path)
    job = _job("review_queued")
    store.save_job(job)
    store.write_token(job.job_id, "review", "token")

    monkeypatch.setattr(
        worker,
        "_claim_credentials",
        lambda *args, **kwargs: (
            {
                "cloudahoy_username": "pilot",
                "cloudahoy_password": "secret",
                "flysto_username": "pilot",
                "flysto_password": "secret",
            },
            False,
        ),
    )
    service = DummyService(store)
    monkeypatch.setattr(worker, "JobService", lambda *_args, **_kwargs: service)

    worker._handle_job(store, job.job_id, "review", None)
    assert service.called == [("review", str(job.job_id))]


def test_handle_job_dispatches_import(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Handle job should call accept_review when purpose is import."""
    store = JobStore(tmp_path)
    job = _job("import_queued")
    store.save_job(job)
    store.write_token(job.job_id, "import", "token")

    monkeypatch.setattr(
        worker,
        "_claim_credentials",
        lambda *args, **kwargs: (
            {
                "cloudahoy_username": "pilot",
                "cloudahoy_password": "secret",
                "flysto_username": "pilot",
                "flysto_password": "secret",
            },
            False,
        ),
    )
    service = DummyService(store)
    monkeypatch.setattr(worker, "JobService", lambda *_args, **_kwargs: service)

    worker._handle_job(store, job.job_id, "import", None)
    assert service.called == [("import", str(job.job_id))]
