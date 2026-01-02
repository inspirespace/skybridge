from __future__ import annotations

import os
import os
import time
from datetime import datetime, timezone
from uuid import UUID

import requests

from .models import JobAcceptRequest, JobCreateRequest
from pathlib import Path

from .object_store import build_object_store_from_env
from .service import JobService
from .store import JobStore

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "data/backend/jobs"))


def _api_url() -> str:
    return (os.environ.get("BACKEND_API_URL") or "http://api:8000").rstrip("/")


def _worker_token() -> str:
    return os.environ.get("BACKEND_WORKER_TOKEN") or ""


def _claim_credentials(job_id: UUID, purpose: str, token: str) -> tuple[dict | None, bool]:
    headers = {"Content-Type": "application/json", "X-Worker-Token": _worker_token()}
    response = requests.post(
        f"{_api_url()}/jobs/{job_id}/credentials/claim",
        json={"purpose": purpose, "token": token},
        headers=headers,
        timeout=15,
    )
    if response.status_code == 503:
        return None, True
    if response.status_code == 410:
        return None, False
    response.raise_for_status()
    payload = response.json()
    creds = payload.get("credentials") if isinstance(payload, dict) else None
    return creds, False


def run() -> None:
    store = JobStore(DATA_DIR, build_object_store_from_env())
    while True:
        jobs = store.list_all_jobs()
        now = datetime.now(timezone.utc).isoformat()
        running = [job for job in jobs if job.status in {"review_running", "import_running"}]
        print(
            f"[worker] {now} total={len(jobs)} running={len(running)}",
            flush=True,
        )
        for job in jobs:
            try:
                if job.status == "review_queued":
                    token = store.read_token(job.job_id, "review")
                    if not token:
                        job.status = "failed"
                        job.error_message = "Missing review token"
                        job.updated_at = datetime.now(timezone.utc)
                        store.save_job(job)
                        continue
                    creds, retry = _claim_credentials(job.job_id, "review", token)
                    if retry:
                        continue
                    store.clear_token(job.job_id, "review")
                    if not creds:
                        job.status = "failed"
                        job.error_message = "Review credentials expired"
                        job.updated_at = datetime.now(timezone.utc)
                        store.save_job(job)
                        continue
                    payload = JobCreateRequest(
                        credentials=creds,
                        start_date=job.start_date,
                        end_date=job.end_date,
                        max_flights=job.max_flights,
                    )
                    JobService(store).generate_review(job.job_id, payload)
                elif job.status == "import_queued":
                    token = store.read_token(job.job_id, "import")
                    if not token:
                        job.status = "failed"
                        job.error_message = "Missing import token"
                        job.updated_at = datetime.now(timezone.utc)
                        store.save_job(job)
                        continue
                    creds, retry = _claim_credentials(job.job_id, "import", token)
                    if retry:
                        continue
                    store.clear_token(job.job_id, "import")
                    if not creds:
                        job.status = "failed"
                        job.error_message = "Import credentials expired"
                        job.updated_at = datetime.now(timezone.utc)
                        store.save_job(job)
                        continue
                    payload = JobAcceptRequest(credentials=creds)
                    JobService(store).accept_review(job.job_id, payload)
            except Exception as exc:
                job.status = "failed"
                job.error_message = f"Worker failed: {exc}"
                job.updated_at = datetime.now(timezone.utc)
                store.save_job(job)
        time.sleep(10)


if __name__ == "__main__":
    run()
