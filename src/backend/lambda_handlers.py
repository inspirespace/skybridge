from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from .models import JobCreateRequest
from .service import JobService
from .store import JobStore

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "/tmp/backend/jobs"))
store = JobStore(DATA_DIR)
service = JobService(store)


def _response(status_code: int, payload: Any) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def _user_id(event: dict[str, Any]) -> str:
    headers = event.get("headers") or {}
    return headers.get("X-User-Id") or headers.get("x-user-id") or ""


def create_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    body = json.loads(event.get("body") or "{}")
    JobCreateRequest.model_validate(body)
    job = service.create_job(user_id)
    job = service.generate_review(job.job_id)
    return _response(201, job.model_dump())


def list_jobs_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    jobs = store.list_jobs(user_id)
    return _response(200, {"jobs": [job.model_dump() for job in jobs]})


def get_job_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    job_id = event.get("pathParameters", {}).get("job_id")
    if not job_id:
        return _response(404, {"detail": "Job not found"})
    job = store.load_job(UUID(job_id))
    if job.user_id != user_id:
        return _response(404, {"detail": "Job not found"})
    return _response(200, job.model_dump())


def accept_review_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    job_id = event.get("pathParameters", {}).get("job_id")
    if not job_id:
        return _response(404, {"detail": "Job not found"})
    job = store.load_job(UUID(job_id))
    if job.user_id != user_id:
        return _response(404, {"detail": "Job not found"})
    if job.status != "review_ready":
        return _response(409, {"detail": "Review not ready"})
    job = service.accept_review(UUID(job_id))
    return _response(200, job.model_dump())


def list_artifacts_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    job_id = event.get("pathParameters", {}).get("job_id")
    if not job_id:
        return _response(404, {"detail": "Job not found"})
    job = store.load_job(UUID(job_id))
    if job.user_id != user_id:
        return _response(404, {"detail": "Job not found"})
    artifacts = store.list_artifacts(UUID(job_id))
    return _response(200, {"artifacts": artifacts})


def read_artifact_handler(event: dict[str, Any], _context: Any) -> dict[str, Any]:
    user_id = _user_id(event)
    if not user_id:
        return _response(401, {"detail": "Missing X-User-Id header"})
    params = event.get("pathParameters") or {}
    job_id = params.get("job_id")
    artifact_name = params.get("artifact_name")
    if not job_id or not artifact_name:
        return _response(404, {"detail": "Artifact not found"})
    job = store.load_job(UUID(job_id))
    if job.user_id != user_id:
        return _response(404, {"detail": "Job not found"})
    data = store.load_artifact(UUID(job_id), artifact_name)
    return _response(200, data)
