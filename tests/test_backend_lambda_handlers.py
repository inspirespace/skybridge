"""Tests for lambda handlers."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import json
import pytest

import src.backend.lambda_handlers as handlers
from src.backend.models import JobRecord
from src.backend.store import JobStore


def _event(user_id: str | None, body: dict | None = None, job_id: str | None = None, artifact: str | None = None):
    headers = {"X-User-Id": user_id} if user_id else {}
    params = {}
    if job_id:
        params["job_id"] = job_id
    if artifact:
        params["artifact_name"] = artifact
    return {
        "headers": headers,
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": params,
    }


def _job(status: str, job_id=None):
    now = datetime.now(timezone.utc)
    return JobRecord(
        job_id=job_id or uuid4(),
        user_id="pilot",
        status=status,
        created_at=now,
        updated_at=now,
        progress_log=[],
    )


@pytest.fixture()
def store(tmp_path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    monkeypatch.setattr(handlers, "_store", store)
    monkeypatch.setattr(handlers, "_service", None)
    monkeypatch.setattr(handlers, "_credential_store", None)
    monkeypatch.setattr(handlers, "_pubsub_client", None)
    return store


def test_list_jobs_handler_requires_auth(store):
    response = handlers.list_jobs_handler(_event(None), None)
    assert response["statusCode"] == 401


def test_create_job_handler(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_ready")

    class _DummyService:
        def create_job(self, user_id: str):
            return job

    class _DummyCredentialStore:
        def issue(self, **_kwargs):
            return "token"

    monkeypatch.setattr(handlers, "_service", _DummyService())
    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())

    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    response = handlers.create_job_handler(_event("pilot", payload), None)
    assert response["statusCode"] == 201


def test_get_job_handler_returns_404(store):
    response = handlers.get_job_handler(_event("pilot", job_id=str(uuid4())), None)
    assert response["statusCode"] == 404


def test_accept_review_handler_conflict(store):
    job = _job("review_running")
    store.save_job(job)
    response = handlers.accept_review_handler(
        _event("pilot", {"credentials": {}}, job_id=str(job.job_id)), None
    )
    assert response["statusCode"] == 409


def test_artifact_handlers(store):
    job = _job("review_ready")
    store.save_job(job)
    store.write_artifact(job.job_id, "review.json", {"ok": True})

    list_response = handlers.list_artifacts_handler(_event("pilot", job_id=str(job.job_id)), None)
    assert list_response["statusCode"] == 200

    read_response = handlers.read_artifact_handler(
        _event("pilot", job_id=str(job.job_id), artifact="review.json"),
        None,
    )
    assert read_response["statusCode"] == 200


def test_delete_job_handler(store):
    job = _job("review_ready")
    store.save_job(job)
    response = handlers.delete_job_handler(_event("pilot", job_id=str(job.job_id)), None)
    assert response["statusCode"] == 200
