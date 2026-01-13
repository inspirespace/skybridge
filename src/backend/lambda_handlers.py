"""src/backend/lambda_handlers.py module."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from .auth import user_id_from_event
from .credential_store import build_credential_store
from .models import CredentialValidationRequest, JobAcceptRequest, JobCreateRequest
from .object_store import build_object_store_from_env
from .service import JobService, validate_credentials
from .store import JobStore


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
        job = store.load_job(job_uuid)
    except (FileNotFoundError, ValueError, ValidationError):
        return None
    if job.user_id != user_id:
        return None
    return job


def _dynamo_jobs_table() -> str | None:
    """Internal helper for dynamo jobs table."""
    if (os.getenv("BACKEND_DYNAMO_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}:
        table = os.getenv("DYNAMO_JOBS_TABLE") or None
        if not table:
            raise RuntimeError("DYNAMO_JOBS_TABLE is required when BACKEND_DYNAMO_ENABLED=1")
        return table
    return None


def _credential_ttl() -> int:
    """Internal helper for credential ttl."""
    return int(os.getenv("BACKEND_CREDENTIAL_TTL") or "900")


def _use_queue() -> bool:
    """Internal helper for use queue."""
    return (os.getenv("BACKEND_SQS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def _sqs_queue_url() -> str:
    """Internal helper for sqs queue url."""
    return os.getenv("SQS_QUEUE_URL") or ""


def _sqs_region() -> str:
    """Internal helper for sqs region."""
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

def _sqs_endpoint_url() -> str | None:
    """Internal helper for sqs endpoint url."""
    value = os.getenv("SQS_ENDPOINT_URL")
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _get_sqs_client():
    """Internal helper for get sqs client."""
    global _sqs_client
    if _sqs_client is None:
        import boto3

        _sqs_client = boto3.client(
            "sqs",
            region_name=_sqs_region(),
            endpoint_url=_sqs_endpoint_url(),
        )
    return _sqs_client


class LambdaHttpError(Exception):
    """Lambda-friendly HTTP error."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _enqueue_job(job_id: UUID, purpose: str, token: str) -> None:
    """Internal helper for enqueue job."""
    if not _use_queue():
        return
    queue_url = _sqs_queue_url()
    if not queue_url:
        raise LambdaHttpError(500, "SQS_QUEUE_URL not configured")
    _get_sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({"job_id": str(job_id), "purpose": purpose, "token": token}),
    )


def _set_queued(job, *, phase: str) -> None:
    """Internal helper for queued status updates."""
    job.status = f"{phase}_queued"
    job.progress_percent = 5
    job.progress_stage = "Queued"
    job.updated_at = datetime.now(timezone.utc)
    job.progress_log.append(
        {
            "phase": phase,
            "stage": "Queued",
            "percent": 5,
            "status": job.status,
            "created_at": job.updated_at,
        }
    )


def _handle_error(exc: Exception) -> dict[str, Any]:
    """Normalize handler errors into API responses."""
    if isinstance(exc, LambdaHttpError):
        return _response(exc.status_code, {"detail": exc.detail})
    if isinstance(exc, ValidationError):
        return _response(400, {"detail": exc.errors()})
    return _response(500, {"detail": str(exc)})


DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "/tmp/backend/jobs"))
store = JobStore(DATA_DIR, build_object_store_from_env(), _dynamo_jobs_table())
service = JobService(store)
credential_store = build_credential_store()
_sqs_client = None


def create_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Create job handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        body = json.loads(event.get("body") or "{}")
        payload = JobCreateRequest.model_validate(body)
        store.delete_jobs_for_user(user_id)
        job = service.create_job(user_id)
        job.start_date = payload.start_date
        job.end_date = payload.end_date
        job.max_flights = payload.max_flights
        token = credential_store.issue(
            job_id=str(job.job_id),
            purpose="review",
            credentials=payload.credentials.model_dump(),
            ttl_seconds=_credential_ttl(),
        )
        _set_queued(job, phase="review")
        store.save_job(job)
        store.write_token(job.job_id, "review", token)
        _enqueue_job(job.job_id, "review", token)
        return _response(201, job.model_dump())
    except Exception as exc:
        return _handle_error(exc)


def list_jobs_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Handle list jobs handler."""
    try:
        user_id = _user_id(event)
        if not user_id:
            return _response(401, {"detail": "Missing authentication"})
        jobs = store.list_jobs(user_id)
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
        review_path = store.job_dir(job.job_id) / "review.json"
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
                and review_path.exists()
                and not has_import_events
            ):
                return _response(409, {"detail": "Review not ready"})
        body = json.loads(event.get("body") or "{}")
        payload = JobAcceptRequest.model_validate(body)
        token = credential_store.issue(
            job_id=str(job.job_id),
            purpose="import",
            credentials=payload.credentials.model_dump(),
            ttl_seconds=_credential_ttl(),
        )
        _set_queued(job, phase="import")
        store.save_job(job)
        store.write_token(job.job_id, "import", token)
        _enqueue_job(job.job_id, "import", token)
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
        artifacts = store.list_artifacts(job.job_id)
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
        data = store.load_artifact(job.job_id, artifact_name)
        return _response(200, data)
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
        store.delete_job(job.job_id, user_id=user_id)
        return _response(200, {"deleted": True})
    except Exception as exc:
        return _handle_error(exc)


def auth_token_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Exchange or refresh OIDC tokens via the provider."""
    try:
        token_url = os.getenv("AUTH_TOKEN_URL") or ""
        if not token_url:
            return _response(500, {"detail": "AUTH_TOKEN_URL not configured"})
        body = json.loads(event.get("body") or "{}")
        refresh_token = body.get("refresh_token")
        code = body.get("code")
        verifier = body.get("code_verifier")
        redirect_uri = body.get("redirect_uri")
        client_id = os.getenv("AUTH_CLIENT_ID") or ""
        if refresh_token:
            data = {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "refresh_token": refresh_token,
            }
        else:
            if not code or not verifier or not redirect_uri:
                return _response(400, {"detail": "Missing code verifier or redirect"})
            data = {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "code": code,
                "redirect_uri": redirect_uri,
                "code_verifier": verifier,
            }
        import requests

        response = requests.post(token_url, data=data, timeout=15)
        if not response.ok:
            return _response(response.status_code, {"detail": response.text})
        return _response(200, response.json())
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

        job_dir = store.job_dir(job_uuid)
        if not job_dir.exists() and not store.object_store:
            return _response(404, {"detail": "Job not found"})

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
        temp_file.close()

        exports_dir = job_dir / "work" / "cloudahoy_exports"
        with zipfile.ZipFile(temp_file.name, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
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

        with open(temp_file.name, "rb") as handle:
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
    except Exception as exc:
        return _handle_error(exc)


def sqs_worker_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    """Process queued review/import jobs from SQS."""
    records = event.get("Records") or []
    for record in records:
        body = record.get("body") or "{}"
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        job_id = payload.get("job_id")
        purpose = payload.get("purpose")
        token = payload.get("token")
        if not job_id or purpose not in {"review", "import"}:
            continue
        try:
            job_uuid = UUID(job_id)
        except ValueError:
            continue
        try:
            job = store.load_job(job_uuid)
        except FileNotFoundError:
            continue
        creds = None
        if token:
            creds = credential_store.claim(token, str(job_uuid), purpose)
        if not creds:
            if job.status in {"review_running", "review_ready", "import_running", "completed"}:
                continue
            job.status = "failed"
            job.error_message = f"{purpose.title()} credentials expired"
            job.updated_at = datetime.now(timezone.utc)
            store.save_job(job)
            continue
        try:
            if purpose == "review":
                payload = JobCreateRequest(
                    credentials=creds,
                    start_date=job.start_date,
                    end_date=job.end_date,
                    max_flights=job.max_flights,
                )
                service.generate_review(job_uuid, payload)
            else:
                payload = JobAcceptRequest(credentials=creds)
                service.accept_review(job_uuid, payload)
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Worker failed: {exc}"
            job.updated_at = datetime.now(timezone.utc)
            store.save_job(job)
    return {"ok": True}
