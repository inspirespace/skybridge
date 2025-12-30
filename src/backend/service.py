from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from .models import ImportReport, JobRecord, ReviewSummary
from .store import JobStore


class JobService:
    def __init__(self, store: JobStore) -> None:
        self._store = store

    def create_job(self, user_id: str) -> JobRecord:
        job = JobRecord(
            job_id=uuid4(),
            user_id=user_id,
            status="review_running",
            created_at=_now(),
            updated_at=_now(),
        )
        self._store.save_job(job)
        return job

    def generate_review(self, job_id: UUID) -> JobRecord:
        job = self._store.load_job(job_id)
        review = ReviewSummary(
            flight_count=0,
            total_hours=0.0,
            earliest_date=None,
            latest_date=None,
            missing_tail_numbers=0,
            flights=[],
        )
        job.review_summary = review
        job.status = "review_ready"
        job.updated_at = _now()
        self._store.save_job(job)
        self._store.write_artifact(job_id, "review-summary.json", review.model_dump())
        return job

    def accept_review(self, job_id: UUID) -> JobRecord:
        job = self._store.load_job(job_id)
        job.status = "import_running"
        job.updated_at = _now()
        self._store.save_job(job)

        report = ImportReport(imported_count=0, skipped_count=0, failed_count=0)
        job.import_report = report
        job.status = "completed"
        job.updated_at = _now()
        self._store.save_job(job)
        self._store.write_artifact(job_id, "import-report.json", report.model_dump())
        return job


def _now() -> datetime:
    return datetime.now(timezone.utc)
