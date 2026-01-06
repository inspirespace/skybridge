"""FastAPI entrypoint for the Skybridge backend.

Responsibilities:
- HTTP API for jobs, artifacts, and auth exchange
- SSE stream for live job updates (with polling fallback on the UI)
- Queueing review/import work for the worker (SQS-backed in prod)
"""
from __future__ import annotations

import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from concurrent.futures import ThreadPoolExecutor

import requests
import asyncio
import json as jsonlib
from fastapi import FastAPI, Header, HTTPException, BackgroundTasks
from fastapi import Request
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import ValidationError

from .auth import user_id_from_request
from .credential_store import build_credential_store
from .models import (
    ArtifactListResponse,
    JobAcceptRequest,
    JobCreateRequest,
    JobListResponse,
    JobRecord,
)
from .object_store import build_object_store_from_env
from .service import JobService
from .store import JobStore
from .web import landing_page
from .rate_limit import RateLimiter

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "/tmp/backend/jobs"))

app = FastAPI(title="Skybridge Backend Dev API")

_ENV = (os.getenv("ENV") or "dev").lower()
if _ENV == "prod":
    if not _use_worker() or not _use_queue():
        raise RuntimeError(
            "Production requires BACKEND_USE_WORKER=1 and BACKEND_SQS_ENABLED=1"
        )

_jobs_rate_limiter = RateLimiter(
    window_seconds=int(os.getenv("BACKEND_RATE_WINDOW") or "60"),
    max_events=int(os.getenv("BACKEND_RATE_JOBS_PER_MIN") or "10"),
)
_accept_rate_limiter = RateLimiter(
    window_seconds=int(os.getenv("BACKEND_RATE_WINDOW") or "60"),
    max_events=int(os.getenv("BACKEND_RATE_ACCEPT_PER_MIN") or "5"),
)
def _dynamo_jobs_table() -> str | None:
    """Internal helper for dynamo jobs table."""
    if (os.getenv("BACKEND_DYNAMO_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}:
        table = os.getenv("DYNAMO_JOBS_TABLE") or None
        if not table:
            raise RuntimeError("DYNAMO_JOBS_TABLE is required when BACKEND_DYNAMO_ENABLED=1")
        return table
    return None


store = JobStore(DATA_DIR, build_object_store_from_env(), _dynamo_jobs_table())
service = JobService(store)
executor = ThreadPoolExecutor(max_workers=int(os.getenv("BACKEND_WORKERS") or "2"))
credential_store = build_credential_store()
_sqs_client = None


def _use_worker() -> bool:
    """Internal helper for use worker."""
    return (os.getenv("BACKEND_USE_WORKER") or "false").lower() in {"1", "true", "yes", "on"}


def _use_queue() -> bool:
    """Internal helper for use queue."""
    return (os.getenv("BACKEND_SQS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def _credential_ttl() -> int:
    """Internal helper for credential ttl."""
    return int(os.getenv("BACKEND_CREDENTIAL_TTL") or "900")


def _worker_token() -> str:
    """Internal helper for worker token."""
    return os.getenv("BACKEND_WORKER_TOKEN") or ""


def _sqs_queue_url() -> str:
    """Internal helper for sqs queue url."""
    return os.getenv("SQS_QUEUE_URL") or ""


def _sqs_region() -> str:
    """Internal helper for sqs region."""
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def _get_sqs_client():
    """Internal helper for get sqs client."""
    global _sqs_client
    if _sqs_client is None:
        import boto3

        _sqs_client = boto3.client("sqs", region_name=_sqs_region())
    return _sqs_client


def _enqueue_job(job_id: UUID, purpose: str, token: str) -> None:
    """Internal helper for enqueue job."""
    if not _use_queue():
        return
    queue_url = _sqs_queue_url()
    if not queue_url:
        raise HTTPException(status_code=500, detail="SQS_QUEUE_URL not configured")
    _get_sqs_client().send_message(
        QueueUrl=queue_url,
        MessageBody=jsonlib.dumps({"job_id": str(job_id), "purpose": purpose, "token": token}),
    )


def _load_job_or_404(job_id: UUID, user_id: str) -> JobRecord:
    """Internal helper for load job or 404."""
    try:
        job = store.load_job(job_id)
    except (FileNotFoundError, ValidationError, ValueError):
        raise HTTPException(status_code=404, detail="Job not found") from None
    if job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _enforce_job_limits(user_id: str, *, for_import: bool) -> None:
    """Internal helper for enforce job limits."""
    max_active = int(os.getenv("BACKEND_MAX_ACTIVE_JOBS") or "1")
    jobs = store.list_jobs(user_id)
    if for_import:
        active = [
            job
            for job in jobs
            if job.status in {"import_queued", "import_running"}
        ]
        if len(active) >= max_active:
            raise HTTPException(
                status_code=429,
                detail="An import is already running for this account.",
            )
        return
    active = [
        job
        for job in jobs
        if job.status in {"review_queued", "review_running"}
    ]
    if len(active) >= max_active:
        raise HTTPException(
            status_code=429,
            detail="A review is already running for this account.",
        )


@app.get("/", include_in_schema=False)
def index() -> object:
    """Handle index."""
    return landing_page()


@app.get("/auth/callback", include_in_schema=False)
def auth_callback() -> object:
    """Handle auth callback."""
    return landing_page()


@app.post("/auth/token", include_in_schema=False)
def auth_token(payload: dict) -> dict:
    """Handle auth token."""
    token_url = os.getenv("AUTH_TOKEN_URL") or ""
    if not token_url:
        raise HTTPException(status_code=500, detail="AUTH_TOKEN_URL not configured")
    refresh_token = payload.get("refresh_token")
    code = payload.get("code")
    verifier = payload.get("code_verifier")
    redirect_uri = payload.get("redirect_uri")
    client_id = os.getenv("AUTH_CLIENT_ID") or "skybridge-dev"
    if refresh_token:
        data = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
        }
    else:
        if not code or not verifier or not redirect_uri:
            raise HTTPException(
                status_code=400, detail="Missing code verifier or redirect"
            )
        data = {
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
        }
    try:
        response = requests.post(
            token_url,
            data=data,
            timeout=15,
        )
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}") from exc
    if not response.ok:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    return response.json()


@app.post("/jobs", response_model=JobRecord)
def create_job(
    payload: JobCreateRequest,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobRecord:
    """Create job."""
    user_id = user_id_from_request(authorization, x_user_id)
    if not _jobs_rate_limiter.allow(f"{user_id}:create"):
        raise HTTPException(status_code=429, detail="Too many requests. Try again soon.")
    _enforce_job_limits(user_id, for_import=False)
    store.delete_jobs_for_user(user_id)
    job = service.create_job(user_id)
    job.start_date = payload.start_date
    job.end_date = payload.end_date
    job.max_flights = payload.max_flights
    if _use_worker() or _use_queue():
        token = credential_store.issue(
            job_id=str(job.job_id),
            purpose="review",
            credentials=payload.credentials.model_dump(),
            ttl_seconds=_credential_ttl(),
        )
        job.status = "review_queued"
        job.progress_percent = 5
        job.progress_stage = "Queued"
        job.updated_at = datetime.now(timezone.utc)
        job.progress_log.append(
            {
                "phase": "review",
                "stage": "Queued",
                "percent": 5,
                "status": "review_queued",
                "created_at": job.updated_at,
            }
        )
        store.save_job(job)
        store.write_token(job.job_id, "review", token)
        _enqueue_job(job.job_id, "review", token)
    else:
        executor.submit(service.generate_review, job.job_id, payload)
    return job


@app.get("/jobs", response_model=JobListResponse)
def list_jobs(
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobListResponse:
    """Handle list jobs."""
    user_id = user_id_from_request(authorization, x_user_id)
    jobs = store.list_jobs(user_id)
    return JobListResponse(jobs=jobs)


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(
    job_id: UUID,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobRecord:
    """Get job."""
    user_id = user_id_from_request(authorization, x_user_id)
    return _load_job_or_404(job_id, user_id)


@app.get("/jobs/{job_id}/events")
async def job_events(
    job_id: UUID,
    request: Request,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> StreamingResponse:
    """Handle job events."""
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)

    async def event_stream():
        """Handle event stream."""
        last_payload = None
        while True:
            if await request.is_disconnected():
                break
            job = _load_job_or_404(job_id, user_id)
            payload = jsonlib.dumps(job.model_dump(mode="json"))
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            if job.status in {"review_ready", "completed", "failed"}:
                break
            await asyncio.sleep(2)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.delete("/jobs/{job_id}")
def delete_job(
    job_id: UUID,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Delete job."""
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)
    store.delete_jobs_for_user(user_id)
    return {"deleted": True}


@app.post("/jobs/{job_id}/review/accept", response_model=JobRecord)
def accept_review(
    job_id: UUID,
    payload: JobAcceptRequest,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobRecord:
    """Handle accept review."""
    user_id = user_id_from_request(authorization, x_user_id)
    if not _accept_rate_limiter.allow(f"{user_id}:accept"):
        raise HTTPException(status_code=429, detail="Too many requests. Try again soon.")
    job = _load_job_or_404(job_id, user_id)
    _enforce_job_limits(user_id, for_import=True)
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
            raise HTTPException(status_code=409, detail="Review not ready")
    if _use_worker() or _use_queue():
        token = credential_store.issue(
            job_id=str(job.job_id),
            purpose="import",
            credentials=payload.credentials.model_dump(),
            ttl_seconds=_credential_ttl(),
        )
        job.status = "import_queued"
        job.progress_percent = 5
        job.progress_stage = "Queued"
        job.updated_at = datetime.now(timezone.utc)
        job.progress_log.append(
            {
                "phase": "import",
                "stage": "Queued",
                "percent": 5,
                "status": "import_queued",
                "created_at": job.updated_at,
            }
        )
        store.save_job(job)
        store.write_token(job.job_id, "import", token)
        _enqueue_job(job.job_id, "import", token)
    else:
        job.status = "import_running"
        job.updated_at = datetime.now(timezone.utc)
        store.save_job(job)
        executor.submit(service.accept_review, job_id, payload)
    return job


@app.post("/jobs/{job_id}/credentials/claim", include_in_schema=False)
def claim_credentials(
    job_id: UUID,
    payload: dict,
    x_worker_token: Optional[str] = Header(default=None),
) -> dict:
    """Handle claim credentials."""
    if not (_use_worker() or _use_queue()):
        raise HTTPException(status_code=409, detail="Worker mode disabled")
    if not _worker_token() or x_worker_token != _worker_token():
        raise HTTPException(status_code=401, detail="Missing worker token")
    purpose = payload.get("purpose")
    token = payload.get("token")
    if purpose not in {"review", "import"} or not token:
        raise HTTPException(status_code=400, detail="Invalid claim payload")
    creds = credential_store.claim(token, str(job_id), purpose)
    if not creds:
        raise HTTPException(status_code=410, detail="Credentials expired")
    return {"credentials": creds}


@app.get("/jobs/{job_id}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(
    job_id: UUID,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> ArtifactListResponse:
    """Handle list artifacts."""
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)
    artifacts = store.list_artifacts(job_id)
    return ArtifactListResponse(artifacts=artifacts)


@app.get("/jobs/{job_id}/artifacts/{artifact_name}")
def read_artifact(
    job_id: UUID,
    artifact_name: str,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """Handle read artifact."""
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)
    artifacts = store.list_artifacts(job_id)
    if artifact_name not in artifacts:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        return store.load_artifact(job_id, artifact_name)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Artifact not found") from None


@app.get("/jobs/{job_id}/artifacts.zip")
def download_artifacts_zip(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> FileResponse:
    """Handle download artifacts zip."""
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)
    job_dir = store.job_dir(job_id)
    if not job_dir.exists() and not store.object_store:
        raise HTTPException(status_code=404, detail="Job not found")

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
            prefix = store.object_store.key_for(user_id, str(job_id), "cloudahoy_exports")
            keys = store.object_store.list_prefix(prefix)
            for key in keys:
                if key.endswith(".token"):
                    continue
                full_key = store.object_store.key_for(
                    user_id,
                    str(job_id),
                    "cloudahoy_exports",
                    key,
                )
                payload = store.object_store.get_bytes(full_key)
                if payload is None:
                    continue
                zipf.writestr(key, payload)

    background_tasks.add_task(os.remove, temp_file.name)
    filename = f"skybridge-run-{job_id}.zip"
    return FileResponse(
        temp_file.name,
        media_type="application/zip",
        filename=filename,
        background=background_tasks,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.backend.app:app", host="0.0.0.0", port=8000, reload=False)
