"""Tests for lambda handlers."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import json
import pytest

from src.backend.firebase_errors import FirestoreDatabaseNotConfiguredError
import src.backend.lambda_handlers as handlers
from src.backend.models import JobRecord, ReviewSummary
from src.backend.store import JobStore


def _event(user_id: str | None, body: dict | None = None, job_id: str | None = None, artifact: str | None = None):
    headers = {"Authorization": f"Bearer {user_id}-token"} if user_id else {}
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


class FakeObjectStore:
    def __init__(self) -> None:
        self.json_payloads: dict[str, dict] = {}
        self.bytes_payloads: dict[str, bytes] = {}

    def key_for(self, *parts: str) -> str:
        return "/".join(parts)

    def list_prefix(self, prefix: str) -> list[str]:
        keys = set()
        for payload_key in self.json_payloads:
            if payload_key.startswith(f"{prefix}/"):
                keys.add(payload_key[len(prefix) + 1 :])
        for payload_key in self.bytes_payloads:
            if payload_key.startswith(f"{prefix}/"):
                keys.add(payload_key[len(prefix) + 1 :])
        return sorted(keys)

    def get_json(self, key: str):
        return self.json_payloads.get(key)

    def get_bytes(self, key: str):
        return self.bytes_payloads.get(key)

    def download_to_file(self, key: str, file_obj) -> bool:
        payload = self.bytes_payloads.get(key)
        if payload is None:
            return False
        file_obj.write(payload)
        return True

    def put_json(self, key: str, payload: dict) -> None:
        self.json_payloads[key] = payload

    def put_file(self, _key: str, _path) -> None:
        return None

    def delete_prefix(self, _prefix: str) -> None:
        return None


@pytest.fixture()
def store(tmp_path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)

    class _DefaultCredentialStore:
        def load_job_credentials(self, _job_id: str):
            return None

        def issue(self, **_kwargs):
            return "token"

    monkeypatch.setattr(handlers, "_store", store)
    monkeypatch.setattr(handlers, "_service", None)
    monkeypatch.setattr(handlers, "_credential_store", _DefaultCredentialStore())
    monkeypatch.setattr(handlers, "_pubsub_client", None)
    monkeypatch.setattr(
        handlers,
        "user_id_from_event",
        lambda event: "pilot"
        if (event.get("headers") or {}).get("Authorization")
        else (_ for _ in ()).throw(Exception("missing auth")),
    )
    return store


def test_list_jobs_handler_requires_auth(store):
    response = handlers.list_jobs_handler(_event(None), None)
    assert response["statusCode"] == 401


def test_list_jobs_handler_surfaces_missing_firestore_database(store, monkeypatch: pytest.MonkeyPatch):
    class _BrokenStore:
        def list_jobs(self, _user_id: str):
            raise FirestoreDatabaseNotConfiguredError("skybridge-inspirespace")

    monkeypatch.setattr(handlers, "_store", _BrokenStore())

    response = handlers.list_jobs_handler(_event("pilot"), None)

    assert response["statusCode"] == 503
    assert "Cloud Firestore is not set up" in response["body"]


def test_create_job_handler(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_ready")
    seen = {}

    class _DummyService:
        def create_job(self, user_id: str):
            seen["create_user_id"] = user_id
            return job

    class _DummyCredentialStore:
        def issue(self, **_kwargs):
            return "token"

    monkeypatch.setattr(handlers, "_service", _DummyService())
    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())
    monkeypatch.setattr(handlers, "_enqueue_job", lambda *args, **kwargs: seen.setdefault("enqueued", True))
    monkeypatch.setattr(
        handlers,
        "resolve_job_queue_topic_path",
        lambda: "projects/demo-project/topics/skybridge-job-queue",
    )

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
    assert seen["create_user_id"] == "pilot"
    assert seen["enqueued"] is True


def test_create_job_handler_requires_worker_queue(store, monkeypatch: pytest.MonkeyPatch):
    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    monkeypatch.setattr(handlers, "resolve_job_queue_topic_path", lambda: None)

    response = handlers.create_job_handler(_event("pilot", payload), None)

    assert response["statusCode"] == 500
    assert "Firebase project id is not configured for the worker queue." in response["body"]


def test_accept_review_handler_enqueues(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_ready")
    job.status = "review_ready"
    store.save_job(job)
    store.write_artifact(job.job_id, "review.json", {"review_id": "review-1", "items": []})

    seen = {}

    class _DummyCredentialStore:
        def issue(self, **_kwargs):
            return "import-token"

    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())
    monkeypatch.setattr(handlers, "_enqueue_job", lambda *args, **kwargs: seen.setdefault("enqueued", True))
    monkeypatch.setattr(
        handlers,
        "resolve_job_queue_topic_path",
        lambda: "projects/demo-project/topics/skybridge-job-queue",
    )

    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    response = handlers.accept_review_handler(
        _event("pilot", payload, job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 200
    assert seen["enqueued"] is True


def test_accept_review_handler_uses_saved_job_credentials_when_request_is_empty(
    store,
    monkeypatch: pytest.MonkeyPatch,
):
    job = _job("review_ready")
    job.status = "review_ready"
    store.save_job(job)
    store.write_artifact(job.job_id, "review.json", {"review_id": "review-1", "items": []})

    seen = {}

    class _DummyCredentialStore:
        def load_job_credentials(self, job_id: str):
            assert job_id == str(job.job_id)
            return {
                "cloudahoy_username": "pilot",
                "cloudahoy_password": "secret",
                "flysto_username": "pilot",
                "flysto_password": "secret",
            }

        def issue(self, **kwargs):
            seen["issued_credentials"] = kwargs["credentials"]
            return "import-token"

    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())
    monkeypatch.setattr(handlers, "_enqueue_job", lambda *args, **kwargs: seen.setdefault("enqueued", True))
    monkeypatch.setattr(
        handlers,
        "resolve_job_queue_topic_path",
        lambda: "projects/demo-project/topics/skybridge-job-queue",
    )

    response = handlers.accept_review_handler(
        _event("pilot", {}, job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 200
    assert seen["enqueued"] is True
    assert seen["issued_credentials"]["flysto_username"] == "pilot"


def test_accept_review_handler_rejects_failed_review_without_import_phase(store):
    job = _job("failed")
    job.review_summary = ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)
    store.write_artifact(job.job_id, "review.json", {"review_id": "review-1", "items": []})

    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    response = handlers.accept_review_handler(
        _event("pilot", payload, job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 409


def test_get_job_handler_marks_stale_queued_job_failed(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_queued")
    job.updated_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    store.save_job(job)
    monkeypatch.setattr(handlers, "QUEUE_STALE_TIMEOUT_SECONDS", 60)

    response = handlers.get_job_handler(_event("pilot", job_id=str(job.job_id)), None)

    assert response["statusCode"] == 200
    assert "worker did not start" in response["body"]


def test_get_job_handler_marks_stale_running_job_failed(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_running")
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    job.updated_at = stale_at
    job.heartbeat_at = stale_at
    store.save_job(job)
    monkeypatch.setenv("BACKEND_RUNNING_STALE_TIMEOUT_SECONDS", "60")

    response = handlers.get_job_handler(_event("pilot", job_id=str(job.job_id)), None)

    assert response["statusCode"] == 200
    assert "worker stalled" in response["body"]


def test_get_job_handler_auto_retries_stale_import_with_saved_credentials(
    store,
    monkeypatch: pytest.MonkeyPatch,
):
    job = _job("import_running")
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    job.updated_at = stale_at
    job.heartbeat_at = stale_at
    job.progress_percent = 85
    job.progress_stage = "Finalizing import"
    job.progress_log = [
        handlers.ProgressEvent(
            phase="import",
            stage="Finalizing import",
            percent=85,
            status="import_running",
            created_at=stale_at,
        )
    ]
    store.save_job(job)

    seen = {}

    class _RetryCredentialStore:
        def load_job_credentials(self, job_id: str):
            assert job_id == str(job.job_id)
            return {
                "cloudahoy_username": "pilot",
                "cloudahoy_password": "secret",
                "flysto_username": "pilot",
                "flysto_password": "secret",
            }

        def issue(self, **kwargs):
            seen["issued"] = kwargs
            return "retry-token"

    monkeypatch.setattr(handlers, "_credential_store", _RetryCredentialStore())
    monkeypatch.setattr(handlers, "_enqueue_job", lambda *args, **kwargs: seen.setdefault("enqueued", True))
    monkeypatch.setenv("BACKEND_RUNNING_STALE_TIMEOUT_SECONDS", "60")

    response = handlers.get_job_handler(_event("pilot", job_id=str(job.job_id)), None)

    assert response["statusCode"] == 200
    assert "\"status\": \"import_queued\"" in response["body"]
    assert "\"worker_retry_count\": 1" in response["body"]
    assert seen["enqueued"] is True
    saved_job = store.load_job(job.job_id)
    assert saved_job.status == "import_queued"
    assert saved_job.worker_retry_count == 1
    assert saved_job.progress_stage == "Retrying import after worker interruption"


def test_get_job_handler_fails_stale_import_after_auto_retry_budget(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("import_running")
    stale_at = datetime.now(timezone.utc) - timedelta(minutes=10)
    job.updated_at = stale_at
    job.heartbeat_at = stale_at
    job.worker_retry_count = 2
    job.progress_log = [
        handlers.ProgressEvent(
            phase="import",
            stage="Finalizing import",
            percent=85,
            status="import_running",
            created_at=stale_at,
        )
    ]
    store.save_job(job)

    monkeypatch.setenv("BACKEND_RUNNING_STALE_TIMEOUT_SECONDS", "60")
    monkeypatch.setenv("BACKEND_STALE_AUTO_RETRY_LIMIT", "2")

    response = handlers.get_job_handler(_event("pilot", job_id=str(job.job_id)), None)

    assert response["statusCode"] == 200
    assert "automatic recovery was exhausted" in response["body"]


def test_create_job_handler_marks_job_failed_when_enqueue_fails(store, monkeypatch: pytest.MonkeyPatch):
    job = _job("review_ready")

    class _DummyService:
        def create_job(self, user_id: str):
            assert user_id == "pilot"
            return job

    class _DummyCredentialStore:
        def issue(self, **_kwargs):
            return "token"

    monkeypatch.setattr(handlers, "_service", _DummyService())
    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())
    monkeypatch.setattr(
        handlers,
        "resolve_job_queue_topic_path",
        lambda: "projects/demo-project/topics/skybridge-job-queue",
    )

    def _raise_enqueue(*_args, **_kwargs):
        raise handlers.LambdaHttpError(500, "publish failed")

    monkeypatch.setattr(handlers, "_enqueue_job", _raise_enqueue)

    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    response = handlers.create_job_handler(_event("pilot", payload), None)

    assert response["statusCode"] == 500
    saved_job = store.load_job(job.job_id)
    assert saved_job.status == "failed"
    assert saved_job.error_message == "publish failed"

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


def test_accept_review_handler_allows_failed_retry_with_remote_review_manifest(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    monkeypatch.setattr(handlers, "_store", store)
    monkeypatch.setattr(handlers, "_service", None)
    monkeypatch.setattr(handlers, "_credential_store", None)
    monkeypatch.setattr(handlers, "_pubsub_client", None)
    monkeypatch.setattr(
        handlers,
        "user_id_from_event",
        lambda event: "pilot"
        if (event.get("headers") or {}).get("Authorization")
        else (_ for _ in ()).throw(Exception("missing auth")),
    )

    job = _job("failed")
    job.review_summary = ReviewSummary(flight_count=0, total_hours=0.0, flights=[])
    job.progress_log = [
        handlers.ProgressEvent(
            phase="import",
            stage="Import failed",
            percent=42,
            status="failed",
            created_at=datetime.now(timezone.utc),
        )
    ]
    store.save_job(job)
    object_store.put_json(
        object_store.key_for(job.user_id, str(job.job_id), "review.json"),
        {"review_id": "review-1", "items": []},
    )

    class _DummyCredentialStore:
        def issue(self, **_kwargs):
            return "import-token"

    seen = {}
    monkeypatch.setattr(handlers, "_credential_store", _DummyCredentialStore())
    monkeypatch.setattr(handlers, "_enqueue_job", lambda *args, **kwargs: seen.setdefault("enqueued", True))
    monkeypatch.setattr(
        handlers,
        "resolve_job_queue_topic_path",
        lambda: "projects/demo-project/topics/skybridge-job-queue",
    )

    payload = {
        "credentials": {
            "cloudahoy_username": "pilot",
            "cloudahoy_password": "secret",
            "flysto_username": "pilot",
            "flysto_password": "secret",
        }
    }
    response = handlers.accept_review_handler(
        _event("pilot", payload, job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 200
    assert seen["enqueued"] is True

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


def test_download_artifacts_zip_merges_remote_exports_with_local_cache(tmp_path, monkeypatch: pytest.MonkeyPatch):
    import zipfile

    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job("completed")
    store.save_job(job)
    monkeypatch.setattr(handlers, "_store", store)
    monkeypatch.setattr(
        handlers,
        "user_id_from_event",
        lambda event: "pilot"
        if (event.get("headers") or {}).get("Authorization")
        else (_ for _ in ()).throw(Exception("missing auth")),
    )

    exports_dir = store.job_dir(job.job_id) / "work" / "cloudahoy_exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "flight-1.gpx").write_text("local-stale")

    remote_prefix = object_store.key_for(job.user_id, str(job.job_id), "cloudahoy_exports")
    object_store.bytes_payloads[f"{remote_prefix}/flight-1.gpx"] = b"remote-fresh"
    object_store.bytes_payloads[f"{remote_prefix}/flight-2.gpx"] = b"remote-second"

    response = handlers.download_artifacts_zip_handler(
        _event("pilot", job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 200
    assert response["bodyFilePath"]
    with zipfile.ZipFile(response["bodyFilePath"], "r") as archive:
        assert sorted(archive.namelist()) == ["flight-1.gpx", "flight-2.gpx"]
        assert archive.read("flight-1.gpx") == b"remote-fresh"
        assert archive.read("flight-2.gpx") == b"remote-second"
    Path(response["bodyFilePath"]).unlink(missing_ok=True)


def test_download_artifacts_zip_falls_back_to_local_when_remote_object_is_missing(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
):
    import zipfile

    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job = _job("completed")
    store.save_job(job)
    monkeypatch.setattr(handlers, "_store", store)
    monkeypatch.setattr(
        handlers,
        "user_id_from_event",
        lambda event: "pilot"
        if (event.get("headers") or {}).get("Authorization")
        else (_ for _ in ()).throw(Exception("missing auth")),
    )

    exports_dir = store.job_dir(job.job_id) / "work" / "cloudahoy_exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "flight-1.gpx").write_text("local-fallback")

    original_list_prefix = object_store.list_prefix
    remote_prefix = object_store.key_for(job.user_id, str(job.job_id), "cloudahoy_exports")
    monkeypatch.setattr(
        object_store,
        "list_prefix",
        lambda prefix: ["flight-1.gpx"] if prefix == remote_prefix else original_list_prefix(prefix),
    )

    response = handlers.download_artifacts_zip_handler(
        _event("pilot", job_id=str(job.job_id)),
        None,
    )

    assert response["statusCode"] == 200
    assert response["bodyFilePath"]
    with zipfile.ZipFile(response["bodyFilePath"], "r") as archive:
        assert archive.namelist() == ["flight-1.gpx"]
        assert archive.read("flight-1.gpx") == b"local-fallback"
    Path(response["bodyFilePath"]).unlink(missing_ok=True)


def test_delete_job_handler(store):
    job = _job("review_ready")
    store.save_job(job)
    seen = {}

    class _DummyCredentialStore:
        def delete_all_for_job(self, job_id: str):
            seen["job_id"] = job_id

    handlers._credential_store = None
    store_obj = _DummyCredentialStore()
    handlers._credential_store = store_obj
    response = handlers.delete_job_handler(_event("pilot", job_id=str(job.job_id)), None)
    assert response["statusCode"] == 200
    assert seen["job_id"] == str(job.job_id)
