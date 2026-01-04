from __future__ import annotations

import os
import time
import json
from datetime import datetime, timezone
from uuid import UUID

import requests

from .models import JobAcceptRequest, JobCreateRequest
from pathlib import Path

from .object_store import build_object_store_from_env
from .service import JobService
from .store import JobStore

DATA_DIR = Path(os.environ.get("BACKEND_DATA_DIR", "data/backend/jobs"))
_sqs_client = None


def _api_url() -> str:
    return (os.environ.get("BACKEND_API_URL") or "http://api:8000").rstrip("/")


def _worker_token() -> str:
    return os.environ.get("BACKEND_WORKER_TOKEN") or ""


def _use_queue() -> bool:
    return (os.getenv("BACKEND_SQS_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}


def _queue_url() -> str:
    return os.getenv("SQS_QUEUE_URL") or ""


def _dynamo_jobs_table() -> str | None:
    if (os.getenv("BACKEND_DYNAMO_ENABLED") or "false").lower() in {"1", "true", "yes", "on"}:
        table = os.getenv("DYNAMO_JOBS_TABLE") or None
        if not table:
            raise RuntimeError("DYNAMO_JOBS_TABLE is required when BACKEND_DYNAMO_ENABLED=1")
        return table
    return None


def _sqs_region() -> str:
    return os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"


def _get_sqs_client():
    global _sqs_client
    if _sqs_client is None:
        import boto3

        _sqs_client = boto3.client("sqs", region_name=_sqs_region())
    return _sqs_client


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


def _handle_job(store: JobStore, job_id: UUID, purpose: str, token: str | None) -> None:
    job = store.load_job(job_id)
    token = token or store.read_token(job.job_id, purpose)
    if not token:
        job.status = "failed"
        job.error_message = f"Missing {purpose} token"
        job.updated_at = datetime.now(timezone.utc)
        store.save_job(job)
        return
    creds, retry = _claim_credentials(job.job_id, purpose, token)
    if retry:
        return
    store.clear_token(job.job_id, purpose)
    if not creds:
        job.status = "failed"
        job.error_message = f"{purpose.title()} credentials expired"
        job.updated_at = datetime.now(timezone.utc)
        store.save_job(job)
        return
    if purpose == "review":
        payload = JobCreateRequest(
            credentials=creds,
            start_date=job.start_date,
            end_date=job.end_date,
            max_flights=job.max_flights,
        )
        JobService(store).generate_review(job.job_id, payload)
    elif purpose == "import":
        payload = JobAcceptRequest(credentials=creds)
        JobService(store).accept_review(job.job_id, payload)


def run() -> None:
    env = (os.getenv("ENV") or "dev").lower()
    if env == "prod" and not _use_queue():
        raise RuntimeError("Production requires BACKEND_SQS_ENABLED=1")
    store = JobStore(DATA_DIR, build_object_store_from_env(), _dynamo_jobs_table())
    if _use_queue():
        queue_url = _queue_url()
        if not queue_url:
            raise RuntimeError("SQS_QUEUE_URL not configured")
        while True:
            response = _get_sqs_client().receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=10,
                VisibilityTimeout=900,
            )
            messages = response.get("Messages") or []
            if not messages:
                continue
            for message in messages:
                receipt = message.get("ReceiptHandle")
                try:
                    payload = json.loads(message.get("Body") or "{}")
                    job_id = UUID(payload.get("job_id"))
                    purpose = payload.get("purpose")
                    token = payload.get("token")
                    if purpose not in {"review", "import"}:
                        raise ValueError("Invalid purpose")
                    _handle_job(store, job_id, purpose, token)
                    if receipt:
                        _get_sqs_client().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                except Exception as exc:
                    if receipt:
                        _get_sqs_client().delete_message(QueueUrl=queue_url, ReceiptHandle=receipt)
                    try:
                        job = store.load_job(job_id)
                        job.status = "failed"
                        job.error_message = f"Worker failed: {exc}"
                        job.updated_at = datetime.now(timezone.utc)
                        store.save_job(job)
                    except Exception:
                        pass
        return

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
                    _handle_job(store, job.job_id, "review", None)
                elif job.status == "import_queued":
                    _handle_job(store, job.job_id, "import", None)
            except Exception as exc:
                job.status = "failed"
                job.error_message = f"Worker failed: {exc}"
                job.updated_at = datetime.now(timezone.utc)
                store.save_job(job)
        time.sleep(10)


if __name__ == "__main__":
    run()
