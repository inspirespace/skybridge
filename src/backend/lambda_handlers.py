from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from .auth import user_id_from_event
from .models import JobAcceptRequest, JobCreateRequest
from .service import JobService
from .store import JobStore
from pydantic import ValidationError

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "/tmp/backend/jobs"))
store = JobStore(DATA_DIR)
service = JobService(store)


def _response(status_code: int, payload: Any) -> dict[str, Any]:
"""Internal helper for response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
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


def create_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Create job handler."""
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing authentication"})
    body = json.loads(event.get("body") or "{}")
    payload = JobCreateRequest.model_validate(body)
    job = service.create_job(user_id)
    job = service.generate_review(job.job_id, payload)
    return _response(201, job.model_dump())


def list_jobs_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Handle list jobs handler."""
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing authentication"})
    jobs = store.list_jobs(user_id)
    return _response(200, {"jobs": [job.model_dump() for job in jobs]})


def get_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Get job handler."""
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


def accept_review_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Handle accept review handler."""
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing authentication"})
    job_id = event.get("pathParameters", {}).get("job_id")
    if not job_id:
        return _response(404, {"detail": "Job not found"})
    job = _load_job(job_id, user_id)
    if not job:
        return _response(404, {"detail": "Job not found"})
    if job.status != "review_ready":
        return _response(409, {"detail": "Review not ready"})
    body = json.loads(event.get("body") or "{}")
    payload = JobAcceptRequest.model_validate(body)
    job = service.accept_review(UUID(job_id), payload)
    return _response(200, job.model_dump())


def list_artifacts_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Handle list artifacts handler."""
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


def read_artifact_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Handle read artifact handler."""
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


def delete_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
"""Delete job handler."""
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing authentication"})
    job_id = event.get("pathParameters", {}).get("job_id")
    if not job_id:
        return _response(404, {"detail": "Job not found"})
    job = _load_job(job_id, user_id)
    if not job:
        return _response(404, {"detail": "Job not found"})
    store.delete_job(job.job_id)
    return _response(200, {"deleted": True})
