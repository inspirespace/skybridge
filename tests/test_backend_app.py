"""Tests for FastAPI backend routes."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from src.backend.models import CredentialPayload, JobAcceptRequest, JobCreateRequest, JobRecord, ReviewSummary
from src.backend.service import JobService
from src.backend.store import JobStore
import src.backend.app as backend_app
import zipfile
import io


class DummyExecutor:
    """Capture background submissions without running them."""
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple, dict]] = []

    def submit(self, fn, *args, **kwargs):
        self.submissions.append((fn, args, kwargs))
        return None


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Provide a test client with isolated store/service."""
    store = JobStore(tmp_path)
    service = JobService(store)
    executor = DummyExecutor()

    monkeypatch.setenv("BACKEND_USE_WORKER", "0")
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "0")
    monkeypatch.setattr(backend_app, "store", store)
    monkeypatch.setattr(backend_app, "service", service)
    monkeypatch.setattr(backend_app, "executor", executor)

    return TestClient(backend_app.app), store, executor


def _make_job(job_id: UUID, user_id: str, status: str) -> JobRecord:
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=job_id,
        user_id=user_id,
        status=status,
        created_at=now,
        updated_at=now,
        progress_log=[],
    )


def _credentials() -> dict:
    return {
        "cloudahoy_username": "pilot",
        "cloudahoy_password": "secret",
        "flysto_username": "pilot",
        "flysto_password": "secret",
    }


def test_create_job_starts_review(client) -> None:
    """Create job should enqueue review generation for signed-in user."""
    test_client, store, executor = client

    payload = {
        "credentials": _credentials(),
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        "max_flights": 3,
    }
    response = test_client.post(
        "/jobs",
        json=payload,
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["start_date"] == "2026-01-01"
    assert body["end_date"] == "2026-01-05"
    assert body["max_flights"] == 3

    job_id = UUID(body["job_id"])
    job = store.load_job(job_id)
    assert job.user_id == "pilot"
    assert len(executor.submissions) == 1


def test_accept_review_rejects_when_not_ready(client) -> None:
    """Accept review should 409 when review is not ready."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_running")
    store.save_job(job)

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 409


def test_accept_review_marks_import_running(client) -> None:
    """Accept review should switch job to import running in local mode."""
    test_client, store, executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "import_running"
    stored = store.load_job(job_id)
    assert stored.status == "import_running"
    assert len(executor.submissions) == 1


def test_events_stream_emits_payload(client) -> None:
    """Event stream should emit at least one data payload."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)

    with test_client.stream(
        "GET",
        f"/jobs/{job_id}/events",
        headers={"X-User-Id": "pilot"},
    ) as response:
        assert response.status_code == 200
        payload = next(response.iter_text())
    assert payload.startswith("data:")


def test_accept_review_allows_failed_with_summary(client) -> None:
    """Accept review should allow failed review with summary + review.json."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "failed")
    job.review_summary = ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)
    review_path = store.job_dir(job_id) / "review.json"
    review_path.write_text("{}")

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200


def test_list_and_read_artifacts(client) -> None:
    """List artifacts should include stored files and read returns content."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)
    store.write_artifact(job_id, "review-summary.json", {"ok": True})

    response = test_client.get(
        f"/jobs/{job_id}/artifacts",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    assert response.json()["artifacts"] == ["review-summary.json"]

    response = test_client.get(
        f"/jobs/{job_id}/artifacts/review-summary.json",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_delete_job_clears_storage(client) -> None:
    """Delete job removes stored job data."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)

    response = test_client.delete(
        f"/jobs/{job_id}",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    assert store.list_jobs("pilot") == []


def test_auth_token_exchange_success(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth token exchange should forward response payload."""
    test_client, _store, _executor = client

    class DummyResponse:
        ok = True
        status_code = 200

        def json(self):
            return {"access_token": "token"}

        @property
        def text(self):
            return ""

    monkeypatch.setenv("AUTH_TOKEN_URL", "https://auth.example/token")
    monkeypatch.setattr(backend_app.requests, "post", lambda *args, **kwargs: DummyResponse())

    response = test_client.post("/auth/token", json={"refresh_token": "refresh"})
    assert response.status_code == 200
    assert response.json()["access_token"] == "token"


def test_auth_token_exchange_failure(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth token exchange should surface HTTP failures."""
    test_client, _store, _executor = client

    class DummyResponse:
        ok = False
        status_code = 401
        text = "invalid"

    monkeypatch.setenv("AUTH_TOKEN_URL", "https://auth.example/token")
    monkeypatch.setattr(backend_app.requests, "post", lambda *args, **kwargs: DummyResponse())

    response = test_client.post("/auth/token", json={"refresh_token": "refresh"})
    assert response.status_code == 401


def test_download_artifacts_zip_includes_exports(client) -> None:
    """Artifacts zip should include local CloudAhoy exports when present."""
    test_client, store, _executor = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)

    exports_dir = store.job_dir(job_id) / "work" / "cloudahoy_exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    sample_path = exports_dir / "flight.gpx"
    sample_path.write_text("payload")

    response = test_client.get(
        f"/jobs/{job_id}/artifacts.zip",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(response.content))
    assert "flight.gpx" in zf.namelist()


def test_claim_credentials_requires_worker_mode(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Claim credentials should 409 if worker mode disabled."""
    test_client, _store, _executor = client
    monkeypatch.setenv("BACKEND_USE_WORKER", "0")
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "0")

    response = test_client.post(
        f"/jobs/{uuid4()}/credentials/claim",
        json={"purpose": "review", "token": "token"},
    )
    assert response.status_code == 409


def test_claim_credentials_success(client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Claim credentials should return payload when worker token matches."""
    test_client, _store, _executor = client

    class DummyCredentialStore:
        def claim(self, token: str, job_id: str, purpose: str):
            return {"cloudahoy_username": "pilot"}

    monkeypatch.setenv("BACKEND_USE_WORKER", "1")
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "0")
    monkeypatch.setenv("BACKEND_WORKER_TOKEN", "worker-token")
    monkeypatch.setattr(backend_app, "credential_store", DummyCredentialStore())

    response = test_client.post(
        f"/jobs/{uuid4()}/credentials/claim",
        json={"purpose": "review", "token": "token"},
        headers={"X-Worker-Token": "worker-token"},
    )
    assert response.status_code == 200
    assert response.json()["credentials"]["cloudahoy_username"] == "pilot"
