"""Shared queue configuration for Firebase worker jobs."""
from __future__ import annotations

from .env import resolve_project_id

JOB_QUEUE_TOPIC = "skybridge-job-queue"


def resolve_job_queue_topic_path() -> str | None:
    """Resolve the fully qualified Pub/Sub topic path for worker jobs."""
    project_id = resolve_project_id()
    if not project_id:
        return None
    return f"projects/{project_id}/topics/{JOB_QUEUE_TOPIC}"
