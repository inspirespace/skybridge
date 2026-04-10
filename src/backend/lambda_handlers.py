"""src/backend/lambda_handlers.py module."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from .auth import user_id_from_event
from .credential_store import build_credential_store
from .env import resolve_project_id
from .firebase_errors import FirestoreDatabaseNotConfiguredError
from .models import CredentialValidationRequest, JobAcceptRequest, JobCreateRequest, ProgressEvent
from .object_store import build_object_store_from_env
from .queue import resolve_job_queue_topic_path
from .service import JobService, validate_credentials
from .store import JobStore

_logger = logging.getLogger(__name__)
QUEUE_STALE_TIMEOUT_SECONDS = 120
RUNNING_STALE_TIMEOUT_SECONDS = 120


def _json_default(value: Any) -> str:
    """JSON serializer for non-serializable objects."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    return str(value)


def _response(status_code: int, payload: Any) -> dict[str, Any]:
    """Internal helper for response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload, default=_json_default),
    }


def _user_id(event: dict[str, Any]) -> str:
    """Internal helper for user id."""
    try:
        return user_id_from_event(event)
    except Exception:
        return ""


def _load_job(job_id: str, user_id: str):
    """Internal helper for load job."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return None
    try:
        job = _get_store().load_job(job_uuid)
    except (FileNotFoundError, ValueError, ValidationError):
        return None
    if job.user_id != user_id:
        return None
    return job


def _firestore_jobs_collection() -> str | None:
    """Internal helper for Firestore jobs collection."""
    return os.getenv("FIRESTORE_JOBS_COLLECTION") or "skybridge-jobs"


def _credential_ttl() -> int:
    """Internal helper for credential ttl."""
    return int(os.getenv("BACKEND_CREDENTIAL_TTL") or "900")


def _job_credential_ttl() -> int:
    """Internal helper for reusable job credential ttl."""
    return int(os.getenv("BACKEND_JOB_CREDENTIAL_TTL") or "21600")


def _pubsub_topic() -> str:
    """Internal helper for pubsub topic."""
    return resolve_job_queue_topic_path() or ""


def _get_pubsub_client():
    """Internal helper for pubsub client."""
    global _pubsub_client
    if _pubsub_client is None:
        from google.cloud import pubsub_v1

        _pubsub_client = pubsub_v1.PublisherClient()
    return _pubsub_client


class LambdaHttpError(Exception):
    """Lambda-friendly HTTP error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _enqueue_job(job_id: UUID, purpose: str, token: str) -> None:
    """Internal helper for enqueue job."""
    payload = json.dumps({"job_id": str(job_id), "purpose": purpose, "token": token}).encode("utf-8")
    topic = _pubsub_topic()
    if not topic:
        raise LambdaHttpError(500, "Firebase project id is not configured for the worker queue.")
    _get_pubsub_client().publish(topic, payload).result(timeout=10)


def _ensure_worker_queue_ready() -> None:
    """Fail fast when the Firebase worker queue cannot be resolved."""
    if _pubsub_topic():
        return
    raise LambdaHttpError(500, "Firebase project id is not configured for the worker queue.")


def _mark_enqueue_failed(job, *, phase: str, detail: str) -> None:
    """Persist immediate queue handoff failures on the job record."""
    job.status = "failed"
    job.updated_at = datetime.now(timezone.utc)
    job.progress_stage = f"{phase.title()} queue handoff failed"
    job.progress_log.append(
        ProgressEvent(
            phase=phase,
            stage=job.progress_stage,
            percent=job.progress_percent,
            status="failed",
            created_at=job.updated_at,
        )
    )
    job.error_message = detail
    _get_store().save_job(job)


def _running_stale_timeout_seconds() -> int:
    value = os.getenv("BACKEND_RUNNING_STALE_TIMEOUT_SECONDS")
    if not value:
        return RUNNING_STALE_TIMEOUT_SECONDS
    try:
        return int(value)
    except ValueError:
        return RUNNING_STALE_TIMEOUT_SECONDS


def _job_phase(job) -> str | None:
    if job.status.startswith("review"):
        return "review"
    if job.status.startswith("import"):
        return "import"
    return None


def _fail_stale_job(job):
    """Mark queued or running jobs failed when the worker stops making progress."""
    purpose = _job_phase(job)
    if not purpose:
        return job
    if job.status == f"{purpose}_queued":
        timeout_seconds = QUEUE_STALE_TIMEOUT_SECONDS
        failure_stage = f"{purpose.title()} worker did not start"
        failure_message = (
            f"{purpose.title()} worker did not start. Check Firebase Pub/Sub/Eventarc configuration."
        )
    elif job.status == f"{purpose}_running":
        timeout_seconds = _running_stale_timeout_seconds()
        failure_stage = f"{purpose.title()} worker stalled"
        failure_message = (
            f"{purpose.title()} stopped making progress in the background. "
            f"Please retry or start over."
        )
    else:
        return job
    reference_time = job.heartbeat_at or job.updated_at
    age_seconds = (datetime.now(timezone.utc) - reference_time).total_seconds()
    if age_seconds < timeout_seconds:
        return job
    job.updated_at = datetime.now(timezone.utc)
    job.heartbeat_at = job.updated_at
    job.status = "failed"
    job.progress_stage = failure_stage
    job.progress_log.append(
        ProgressEvent(
            phase=purpose,
            stage=job.progress_stage,
            percent=job.progress_percent,
            status="failed",
            created_at=job.updated_at,
        )
    )
    job.error_message = failure_message
    _get_store().save_job(job)
    return job


def _set_queued(job, *, phase: str) -> None:
    """Internal helper for queued status updates."""
    job.status = f"{phase}_queued"
    job.progress_percent = 5
    job.progress_stage = "Queued"
    job.updated_at = datetime.now(timezone.utc)
    job.progress_log.append(
        ProgressEvent(
            phase=phase,
            stage="Queued",
            percent=5,
            status=job.status,
            created_at=job.updated_at,
        )
    )


def _handle_error(exc: Exception) -> dict[str, Any]:
    """Normalize handler errors into API responses.

    SECURITY: Internal exceptions are logged but not exposed to clients.
    Only controlled error messages are returned to prevent information leakage.
    """
    if isinstance(exc, LambdaHttpError):
        return _response(exc.status_code, {"detail": exc.detail})
    if isinstance(exc, FirestoreDatabaseNotConfiguredError):
        return _response(
            503,
            {"detail": "Service configuration error: Cloud Firestore is not set up for this Firebase project."},
        )
    if isinstance(exc, ValidationError):
        return _response(400, {"detail": exc.errors()})
    # Log the actual exception for debugging, but return generic message to client
    _logger.exception("Internal error: %s", exc)
    return _response(500, {"detail": "An internal error occurred. Please try again later."})


DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "/tmp/backend/jobs"))
_store: JobStore | None = None
_service: JobService | None = None
_credential_store = None
_pubsub_client = None
_ACTIVE_JOB_STATUSES = {
    "review_queued",
    "review_running",
    "import_queued",
    "import_running",
}


def _get_store() -> JobStore:
    """Initialize store lazily to keep function discovery lightweight."""
    global _store
    if _store is None:
        _store = JobStore(
            DATA_DIR,
            build_object_store_from_env(),
            firestore_collection=_firestore_jobs_collection(),
            firestore_project=resolve_project_id(),
        )
    return _store


def _get_service() -> JobService:
    """Initialize service lazily."""
    global _service
    if _service is None:
        _service = JobService(_get_store())
    return _service


def _get_credential_store():
    """Initialize credential store lazily."""
    global _credential_store
    if _credential_store is None:
        _credential_store = build_credential_store()
    return _credential_store


def _persist_job_credentials(job_id: str, credentials: dict[str, Any]) -> None:
    """Persist reusable job-scoped credentials when supported by the store."""
    store = _get_credential_store()
    if hasattr(store, "store_job_credentials"):
        store.store_job_credentials(job_id, credentials, _job_credential_ttl())


def _load_job_credentials(job_id: str) -> dict[str, Any] | None:
    """Load reusable job-scoped credentials when supported by the store."""
    store = _get_credential_store()
    if hasattr(store, "load_job_credentials"):
        return store.load_job_credentials(job_id)
    return None


def _delete_job_credentials(job_id: str) -> None:
    """Delete reusable job-scoped credentials when supported by the store."""
    global _credential_store
    store = _credential_store
    if hasattr(store, "delete_job_credentials"):
        store.delete_job_credentials(job_id)


def _credentials_complete(credentials) -> bool:
    """Return True when all required credential fields are present and non-empty."""
    if credentials is None:
        return False
    if hasattr(credentials, "model_dump"):
        payload = credentials.model_dump()
    elif isinstance(credentials, dict):
        payload = credentials
    else:
        return False
    required = (
        "cloudahoy_username",
        "cloudahoy_password",
        "flysto_username",
        "flysto_password",
    )
    return all(isinstance(payload.get(key), str) and payload.get(key).strip() for key in required)


def create_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Create job handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        body = json.loads(event.get("body") or "{}")
        payload = JobCreateRequest.model_validate(body)
        store = _get_store()
        service = _get_service()
        existing_jobs = [_fail_stale_job(job) for job in store.list_jobs(user_id)]
        if any(job.status in _ACTIVE_JOB_STATUSES for job in existing_jobs):
            return _response(429, {"detail": "Job already in progress"})
        _ensure_worker_queue_ready()
        for existing_job in existing_jobs:
            _delete_job_credentials(str(existing_job.job_id))
        store.delete_jobs_for_user(user_id)
        job = service.create_job(user_id)
        job.start_date = payload.start_date
        job.end_date = payload.end_date
        job.max_flights = payload.max_flights
        credentials_payload = payload.credentials.model_dump()
        _persist_job_credentials(str(job.job_id), credentials_payload)
        token = _get_credential_store().issue(
            job_id=str(job.job_id),
            purpose="review",
            credentials=credentials_payload,
            ttl_seconds=_credential_ttl(),
        )
        _set_queued(job, phase="review")
        store.save_job(job)
        store.write_token(job.job_id, "review", token)
        try:
            _enqueue_job(job.job_id, "review", token)
        except LambdaHttpError as exc:
            _mark_enqueue_failed(job, phase="review", detail=exc.detail)
            raise
        except Exception as exc:
            _logger.exception("Failed to enqueue review job %s", job.job_id)
            _mark_enqueue_failed(
                job,
                phase="review",
                detail="Review queue handoff failed. Check Firebase Pub/Sub permissions/configuration.",
            )
            raise LambdaHttpError(
                500,
                "Review queue handoff failed. Check Firebase Pub/Sub permissions/configuration.",
            ) from exc
        return _response(201, job.model_dump())
    except Exception as exc:
        return _handle_error(exc)


def list_jobs_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle list jobs handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        jobs = [_fail_stale_job(job) for job in _get_store().list_jobs(user_id)]
        return _response(200, {"jobs": [job.model_dump() for job in jobs]})
    except Exception as exc:
        return _handle_error(exc)


def validate_credentials_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Validate account credentials handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        body = json.loads(event.get("body") or "{}")
        payload = CredentialValidationRequest.model_validate(body)
        validate_credentials(payload.credentials)
        return _response(200, {"ok": True})
    except RuntimeError as exc:
        return _response(400, {"detail": str(exc)})
    except Exception as exc:
        return _handle_error(exc)


def get_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Get job handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        job_id = event.get("pathParameters", {}).get("job_id")
        if not job_id:
            return _response(404, {"detail": "Job not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        job = _fail_stale_job(job)
        return _response(200, job.model_dump())
    except Exception as exc:
        return _handle_error(exc)


def accept_review_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle accept review handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        job_id = event.get("pathParameters", {}).get("job_id")
        if not job_id:
            return _response(404, {"detail": "Job not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        job = _fail_stale_job(job)
        store = _get_store()
        review_manifest_available = False
        try:
            store.load_artifact(job.job_id, "review.json")
            review_manifest_available = True
        except FileNotFoundError:
            review_manifest_available = False
        has_import_events = any(
            getattr(event, "phase", None) == "import"
            if hasattr(event, "phase")
            else event.get("phase") == "import"
            for event in (job.progress_log or [])
            if event
        )
        if job.status != "review_ready":
            if not (
                job.status == "failed"
                and job.review_summary is not None
                and review_manifest_available
                and has_import_events
            ):
                return _response(409, {"detail": "Review not ready"})
        _ensure_worker_queue_ready()
        body = json.loads(event.get("body") or "{}")
        payload = JobAcceptRequest.model_validate(body)
        provided_credentials = payload.credentials.model_dump() if _credentials_complete(payload.credentials) else None
        if provided_credentials:
            _persist_job_credentials(str(job.job_id), provided_credentials)
        credentials_payload = provided_credentials or _load_job_credentials(str(job.job_id))
        if not _credentials_complete(credentials_payload):
            return _response(
                400,
                {
                    "detail": (
                        "Import credentials are unavailable. Re-enter CloudAhoy and FlySto "
                        "credentials in Connect Accounts and retry."
                    )
                },
            )
        token = _get_credential_store().issue(
            job_id=str(job.job_id),
            purpose="import",
            credentials=credentials_payload,
            ttl_seconds=_credential_ttl(),
        )
        _set_queued(job, phase="import")
        store.save_job(job)
        store.write_token(job.job_id, "import", token)
        try:
            _enqueue_job(job.job_id, "import", token)
        except LambdaHttpError as exc:
            _mark_enqueue_failed(job, phase="import", detail=exc.detail)
            raise
        except Exception as exc:
            _logger.exception("Failed to enqueue import job %s", job.job_id)
            _mark_enqueue_failed(
                job,
                phase="import",
                detail="Import queue handoff failed. Check Firebase Pub/Sub permissions/configuration.",
            )
            raise LambdaHttpError(
                500,
                "Import queue handoff failed. Check Firebase Pub/Sub permissions/configuration.",
            ) from exc
        return _response(200, job.model_dump())
    except Exception as exc:
        return _handle_error(exc)


def list_artifacts_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle list artifacts handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        job_id = event.get("pathParameters", {}).get("job_id")
        if not job_id:
            return _response(404, {"detail": "Job not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        artifacts = _get_store().list_artifacts(job.job_id)
        return _response(200, {"artifacts": artifacts})
    except Exception as exc:
        return _handle_error(exc)


def read_artifact_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle read artifact handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        params = event.get("pathParameters") or {}
        job_id = params.get("job_id")
        artifact_name = params.get("artifact_name")
        if not job_id or not artifact_name:
            return _response(404, {"detail": "Artifact not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        data = _get_store().load_artifact(job.job_id, artifact_name)
        return _response(200, data)
    except (FileNotFoundError, ValueError):
        return _response(404, {"detail": "Artifact not found"})
    except Exception as exc:
        return _handle_error(exc)


def delete_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Delete job handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        job_id = event.get("pathParameters", {}).get("job_id")
        if not job_id:
            return _response(404, {"detail": "Job not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        _delete_job_credentials(str(job.job_id))
        _get_store().delete_job(job.job_id, user_id=user_id)
        return _response(200, {"deleted": True})
    except Exception as exc:
        return _handle_error(exc)


def download_artifacts_zip_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Download artifacts zip handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        params = event.get("pathParameters") or {}
        job_id = params.get("job_id")
        if not job_id:
            return _response(404, {"detail": "Job not found"})
        job = _load_job(job_id, user_id)
        if not job:
            return _response(404, {"detail": "Job not found"})
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            return _response(404, {"detail": "Job not found"})

        import base64
        import tempfile
        import zipfile

        store = _get_store()
        job_dir = store.job_dir(job_uuid)
        if not job_dir.exists() and not store.object_store:
            return _response(404, {"detail": "Job not found"})

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_file.close()
        temp_path = temp_file.name

        try:
            exports_dir = job_dir / "work" / "cloudahoy_exports"
            with zipfile.ZipFile(temp_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                if exports_dir.exists():
                    for path in exports_dir.rglob("*"):
                        if not path.is_file():
                            continue
                        if path.name.endswith(".token"):
                            continue
                        arcname = str(path.relative_to(exports_dir))
                        zipf.write(path, arcname=arcname)
                elif store.object_store:
                    prefix = store.object_store.key_for(user_id, str(job_uuid), "cloudahoy_exports")
                    keys = store.object_store.list_prefix(prefix)
                    for key in keys:
                        if key.endswith(".token"):
                            continue
                        full_key = store.object_store.key_for(
                            user_id,
                            str(job_uuid),
                            "cloudahoy_exports",
                            key,
                        )
                        payload = store.object_store.get_bytes(full_key)
                        if payload is None:
                            continue
                        zipf.writestr(key, payload)

            with open(temp_path, "rb") as handle:
                payload = handle.read()
            encoded = base64.b64encode(payload).decode("utf-8")
            filename = f"skybridge-run-{job_uuid}.zip"
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/zip",
                    "Content-Disposition": f'attachment; filename="{filename}"',
                },
                "isBase64Encoded": True,
                "body": encoded,
            }
        finally:
            # Always clean up the temp file to prevent disk space exhaustion
            try:
                os.unlink(temp_path)
            except OSError:
                pass
    except Exception as exc:
        return _handle_error(exc)


def _process_queue_payload(payload: dict[str, Any]) -> None:
    """Shared worker logic for Pub/Sub payloads."""
    job_id = payload.get("job_id")
    purpose = payload.get("purpose")
    token = payload.get("token")
    if not job_id or purpose not in {"review", "import"}:
        return
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return
    try:
        store = _get_store()
        job = store.load_job(job_uuid)
    except FileNotFoundError:
        return
    creds = None
    if token:
        creds = _get_credential_store().claim(token, str(job_uuid), purpose)
    if not creds:
        if job.status in {"review_running", "review_ready", "import_running", "completed"}:
            return
        job.status = "failed"
        job.error_message = f"{purpose.title()} credentials expired"
        job.updated_at = datetime.now(timezone.utc)
        store.save_job(job)
        return
    try:
        if purpose == "review":
            request = JobCreateRequest(
                credentials=creds,
                start_date=job.start_date,
                end_date=job.end_date,
                max_flights=job.max_flights,
            )
            updated_job = _get_service().generate_review(job_uuid, request)
        else:
            request = JobAcceptRequest(credentials=creds)
            updated_job = _get_service().accept_review(job_uuid, request)
        if (
            updated_job.status == f"{purpose}_running"
            and updated_job.phase_total is not None
            and (updated_job.phase_cursor or 0) < updated_job.phase_total
        ):
            next_token = _get_credential_store().issue(
                job_id=str(updated_job.job_id),
                purpose=purpose,
                credentials=creds,
                ttl_seconds=_credential_ttl(),
            )
            store.write_token(updated_job.job_id, purpose, next_token)
            _enqueue_job(updated_job.job_id, purpose, next_token)
    except Exception as exc:
        job.status = "failed"
        job.error_message = f"Worker failed: {exc}"
        job.updated_at = datetime.now(timezone.utc)
        job.heartbeat_at = job.updated_at
        store.save_job(job)


def pubsub_worker_handler(event: dict[str, Any], _context: Any = None) -> dict[str, Any]:
    """Process queued review/import jobs from Pub/Sub."""
    message = event.get("message") or {}
    data = message.get("data")
    if not data:
        return {"ok": False}
    import base64

    try:
        payload = json.loads(base64.b64decode(data).decode("utf-8"))
    except Exception:
        return {"ok": False}
    _process_queue_payload(payload)
    return {"ok": True}
