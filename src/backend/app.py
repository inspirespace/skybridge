from __future__ import annotations

import os
import os
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import FastAPI, Header, HTTPException
from pydantic import ValidationError

from .models import ArtifactListResponse, JobCreateRequest, JobListResponse, JobRecord
from .service import JobService
from .store import JobStore
from .web import landing_page

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "data/backend/jobs"))

app = FastAPI(title="Skybridge Backend Dev API")
store = JobStore(DATA_DIR)
service = JobService(store)


def _user_id(x_user_id: Optional[str]) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


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


@app.post("/jobs", response_model=JobRecord)
def create_job(payload: JobCreateRequest, x_user_id: Optional[str] = Header(default=None)) -> JobRecord:
    user_id = _user_id(x_user_id)
    job = service.create_job(user_id)
    job = service.generate_review(job.job_id)
    return job


@app.get("/jobs", response_model=JobListResponse)
def list_jobs(x_user_id: Optional[str] = Header(default=None)) -> JobListResponse:
    user_id = _user_id(x_user_id)
    jobs = store.list_jobs(user_id)
    return JobListResponse(jobs=jobs)


@app.get("/jobs/{job_id}", response_model=JobRecord)
def get_job(job_id: UUID, x_user_id: Optional[str] = Header(default=None)) -> JobRecord:
    user_id = _user_id(x_user_id)
    return _load_job_or_404(job_id, user_id)


@app.post("/jobs/{job_id}/review/accept", response_model=JobRecord)
def accept_review(job_id: UUID, x_user_id: Optional[str] = Header(default=None)) -> JobRecord:
    user_id = _user_id(x_user_id)
    job = _load_job_or_404(job_id, user_id)
    if job.status != "review_ready":
        raise HTTPException(status_code=409, detail="Review not ready")
    return service.accept_review(job_id)


@app.get("/jobs/{job_id}/artifacts", response_model=ArtifactListResponse)
def list_artifacts(job_id: UUID, x_user_id: Optional[str] = Header(default=None)) -> ArtifactListResponse:
    user_id = _user_id(x_user_id)
    _load_job_or_404(job_id, user_id)
    artifacts = store.list_artifacts(job_id)
    return ArtifactListResponse(artifacts=artifacts)


@app.get("/jobs/{job_id}/artifacts/{artifact_name}")
def read_artifact(
    job_id: UUID, artifact_name: str, x_user_id: Optional[str] = Header(default=None)
) -> dict:
    user_id = _user_id(x_user_id)
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
