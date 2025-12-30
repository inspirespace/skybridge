from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID

from concurrent.futures import ThreadPoolExecutor

import requests
from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError

from .auth import user_id_from_request
from .models import (
    ArtifactListResponse,
    JobAcceptRequest,
    JobCreateRequest,
    JobListResponse,
    JobRecord,
)
from .service import JobService
from .store import JobStore
from .web import landing_page

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "data/backend/jobs"))

app = FastAPI(title="Skybridge Backend Dev API")
store = JobStore(DATA_DIR)
service = JobService(store)
executor = ThreadPoolExecutor(max_workers=int(os.getenv("BACKEND_WORKERS") or "2"))


def _load_job_or_404(job_id: UUID, user_id: str) -> JobRecord:
    try:
        job = store.load_job(job_id)
    except (FileNotFoundError, ValidationError, ValueError):
        raise HTTPException(status_code=404, detail="Job not found") from None
    if job.user_id != user_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/", include_in_schema=False)
def index() -> object:
    return landing_page()


@app.get("/auth/callback", include_in_schema=False)
def auth_callback() -> object:
    return landing_page()


@app.post("/auth/token", include_in_schema=False)
def auth_token(payload: dict) -> dict:
    token_url = os.getenv("AUTH_TOKEN_URL") or ""
    if not token_url:
        raise HTTPException(status_code=500, detail="AUTH_TOKEN_URL not configured")
    code = payload.get("code")
    verifier = payload.get("code_verifier")
    redirect_uri = payload.get("redirect_uri")
    if not code or not verifier or not redirect_uri:
        raise HTTPException(status_code=400, detail="Missing code verifier or redirect")
    data = {
        "grant_type": "authorization_code",
        "client_id": os.getenv("AUTH_CLIENT_ID") or "skybridge-dev",
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
    user_id = user_id_from_request(authorization, x_user_id)
    job = service.create_job(user_id)
    executor.submit(service.generate_review, job.job_id, payload)
    return job


@app.get("/jobs", response_model=JobListResponse)
def list_jobs(
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobListResponse:
    user_id = user_id_from_request(authorization, x_user_id)
    jobs = store.list_jobs(user_id)
    return JobListResponse(jobs=jobs)


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(
    job_id: UUID,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobRecord:
    user_id = user_id_from_request(authorization, x_user_id)
    return _load_job_or_404(job_id, user_id)


@app.post("/jobs/{job_id}/review/accept", response_model=JobRecord)
def accept_review(
    job_id: UUID,
    payload: JobAcceptRequest,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> JobRecord:
    user_id = user_id_from_request(authorization, x_user_id)
    job = _load_job_or_404(job_id, user_id)
    if job.status != "review_ready":
        raise HTTPException(status_code=409, detail="Review not ready")
    job.status = "import_running"
    job.updated_at = datetime.now(timezone.utc)
    store.save_job(job)
    executor.submit(service.accept_review, job_id, payload)
    return job


@app.get("/jobs/{job_id}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(
    job_id: UUID,
    x_user_id: Optional[str] = Header(default=None),
    authorization: Optional[str] = Header(default=None),
) -> ArtifactListResponse:
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
    user_id = user_id_from_request(authorization, x_user_id)
    _load_job_or_404(job_id, user_id)
    artifacts = store.list_artifacts(job_id)
    if artifact_name not in artifacts:
        raise HTTPException(status_code=404, detail="Artifact not found")
    try:
        return store.load_artifact(job_id, artifact_name)
    except (FileNotFoundError, ValueError):
        raise HTTPException(status_code=404, detail="Artifact not found") from None


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.backend.app:app", host="0.0.0.0", port=8000, reload=False)
