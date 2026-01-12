"""Additional tests for backend app routes."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import src.backend.app as backend_app
from src.backend.models import JobRecord, ReviewSummary
from src.backend.service import JobService
from src.backend.store import JobStore


class DummyExecutor:
    def __init__(self) -> None:
        self.submissions: list[tuple[object, tuple, dict]] = []

    def submit(self, fn, *args, **kwargs):
        self.submissions.append((fn, args, kwargs))
        return None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    store = JobStore(tmp_path)
    service = JobService(store)
    executor = DummyExecutor()

    monkeypatch.setenv("BACKEND_USE_WORKER", "0")
    monkeypatch.setenv("BACKEND_SQS_ENABLED", "0")
    monkeypatch.setattr(backend_app, "store", store)
    monkeypatch.setattr(backend_app, "service", service)
    monkeypatch.setattr(backend_app, "executor", executor)

    return TestClient(backend_app.app), store


def _make_job(job_id, user_id, status):
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=job_id,
        user_id=user_id,
        status=status,
        created_at=now,
        updated_at=now,
        progress_log=[],
    )


def _credentials():
    return {
        "cloudahoy_username": "pilot",
        "cloudahoy_password": "secret",
        "flysto_username": "pilot",
        "flysto_password": "secret",
    }


def test_accept_review_rate_limited(client, monkeypatch):
    test_client, store = client
    job_id = uuid4()
    store.save_job(_make_job(job_id, "pilot", "review_ready"))
    monkeypatch.setattr(backend_app._accept_rate_limiter, "allow", lambda _key: False)

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 429


def test_accept_review_rejects_when_missing_summary(client):
    test_client, store = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "failed")
    store.save_job(job)

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 409


def test_accept_review_queued_when_worker_enabled(client, monkeypatch):
    test_client, store = client
    job_id = uuid4()
    job = _make_job(job_id, "pilot", "review_ready")
    store.save_job(job)

    monkeypatch.setenv("BACKEND_USE_WORKER", "1")

    class DummyStore:
        def __init__(self):
            self.issued = []

        def issue(self, **kwargs):
            self.issued.append(kwargs)
            return "token"

    monkeypatch.setattr(backend_app, "credential_store", DummyStore())

    response = test_client.post(
        f"/jobs/{job_id}/review/accept",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    stored = store.load_job(job_id)
    assert stored.status == "import_queued"


def test_job_events_stream_closes_on_terminal_status(client, monkeypatch):
    test_client, store = client
    job_id = uuid4()
    job_running = _make_job(job_id, "pilot", "review_running")
    job_done = _make_job(job_id, "pilot", "failed")
    store.save_job(job_running)

    jobs = [job_running, job_done]

    def fake_load(*_args, **_kwargs):
        return jobs.pop(0) if jobs else job_done

    monkeypatch.setattr(backend_app, "_load_job_or_404", fake_load)
    async def fake_sleep(*_args, **_kwargs):
        return None

    monkeypatch.setattr(backend_app.asyncio, "sleep", fake_sleep)

    with test_client.stream(
        "GET",
        f"/jobs/{job_id}/events",
        headers={"X-User-Id": "pilot"},
    ) as response:
        assert response.status_code == 200
        first = next(response.iter_text())
    assert first.startswith("data:")


def test_delete_job_requires_user(client):
    test_client, store = client
    job_id = uuid4()
    store.save_job(_make_job(job_id, "pilot", "review_ready"))

    response = test_client.delete(f"/jobs/{job_id}")
    assert response.status_code == 401


def test_delete_job_clears_jobs(client):
    test_client, store = client
    job_id = uuid4()
    store.save_job(_make_job(job_id, "pilot", "review_ready"))

    response = test_client.delete(
        f"/jobs/{job_id}",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert store.list_jobs("pilot") == []


def test_get_job_404s_for_other_user(client):
    test_client, store = client
    job_id = uuid4()
    store.save_job(_make_job(job_id, "pilot", "review_ready"))

    response = test_client.get(
        f"/jobs/{job_id}",
        headers={"X-User-Id": "other"},
    )
    assert response.status_code == 404


def test_auth_token_missing_url(client, monkeypatch):
    test_client, _store = client
    monkeypatch.delenv("AUTH_TOKEN_URL", raising=False)
    response = test_client.post("/auth/token", json={})
    assert response.status_code == 500


def test_auth_token_missing_code_fields(client, monkeypatch):
    test_client, _store = client
    monkeypatch.setenv("AUTH_TOKEN_URL", "https://auth.example/token")
    response = test_client.post("/auth/token", json={})
    assert response.status_code == 400


def test_auth_token_request_error(client, monkeypatch):
    test_client, _store = client
    monkeypatch.setenv("AUTH_TOKEN_URL", "https://auth.example/token")

    def fake_post(*_args, **_kwargs):
        raise backend_app.requests.RequestException("boom")

    monkeypatch.setattr(backend_app.requests, "post", fake_post)
    response = test_client.post("/auth/token", json={"refresh_token": "token"})
    assert response.status_code == 502


def test_auth_token_propagates_failure(client, monkeypatch):
    test_client, _store = client
    monkeypatch.setenv("AUTH_TOKEN_URL", "https://auth.example/token")

    class DummyResponse:
        ok = False
        status_code = 401
        text = "bad"

    monkeypatch.setattr(backend_app.requests, "post", lambda *_a, **_k: DummyResponse())
    response = test_client.post("/auth/token", json={"refresh_token": "token"})
    assert response.status_code == 401


def test_validate_credentials_rate_limited(client, monkeypatch):
    test_client, _store = client
    monkeypatch.setattr(backend_app._validate_rate_limiter, "allow", lambda _key: False)
    response = test_client.post(
        "/credentials/validate",
        json={"credentials": _credentials()},
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 429


def test_claim_credentials_errors(client, monkeypatch):
    test_client, _store = client
    job_id = uuid4()

    monkeypatch.setenv("BACKEND_USE_WORKER", "0")
    response = test_client.post(
        f"/jobs/{job_id}/credentials/claim",
        json={"purpose": "review", "token": "tok"},
    )
    assert response.status_code == 409

    monkeypatch.setenv("BACKEND_USE_WORKER", "1")
    monkeypatch.setenv("BACKEND_WORKER_TOKEN", "tok")
    response = test_client.post(
        f"/jobs/{job_id}/credentials/claim",
        json={"purpose": "review", "token": "tok"},
    )
    assert response.status_code == 401

    response = test_client.post(
        f"/jobs/{job_id}/credentials/claim",
        json={"purpose": "bad", "token": "tok"},
        headers={"X-Worker-Token": "tok"},
    )
    assert response.status_code == 400

    monkeypatch.setattr(backend_app.credential_store, "claim", lambda *_a, **_k: None)
    response = test_client.post(
        f"/jobs/{job_id}/credentials/claim",
        json={"purpose": "review", "token": "tok"},
        headers={"X-Worker-Token": "tok"},
    )
    assert response.status_code == 410


def test_download_artifacts_zip_missing_job(client, monkeypatch, tmp_path):
    test_client, store = client
    job_id = uuid4()
    monkeypatch.setattr(backend_app, "store", store)

    response = test_client.get(
        f"/jobs/{job_id}/artifacts.zip",
        headers={"X-User-Id": "pilot"},
    )
    assert response.status_code == 404
