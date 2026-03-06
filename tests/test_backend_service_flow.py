"""Tests for backend JobService review/import flows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import json
import pytest

from src.backend.models import CredentialPayload, JobAcceptRequest, JobCreateRequest
from src.backend.service import JobService
import src.backend.service as service_mod
from src.backend.store import JobStore
from src.core.models import FlightSummary as CoreFlightSummary, MigrationResult


@dataclass
class FakeReviewItem:
    flight_id: str
    started_at: datetime | None
    duration_seconds: int | None
    tail_number: str | None
    metadata: dict | None
    status: str | None
    message: str | None


class FakeCloudAhoy:
    def __init__(self, summaries: list[CoreFlightSummary]):
        self._summaries = summaries

    def list_flights(self, limit=None):
        return self._summaries


class FakeFlySto:
    def prepare(self) -> bool:
        return True


@pytest.fixture()
def job_service(tmp_path: Path) -> JobService:
    store = JobStore(tmp_path)
    return JobService(store)


def _credentials() -> CredentialPayload:
    return CredentialPayload(
        cloudahoy_username="pilot",
        cloudahoy_password="secret",
        flysto_username="pilot",
        flysto_password="secret",
    )


def test_generate_review_success(job_service: JobService, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Generate review should build summary and artifacts."""
    job = job_service.create_job("pilot")

    summaries = [
        CoreFlightSummary(
            id="flight-1",
            started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aircraft_type="C172",
            tail_number="N123",
        )
    ]

    def fake_build_cloudahoy(payload, exports_dir: Path):
        exports_dir.mkdir(parents=True, exist_ok=True)
        return FakeCloudAhoy(summaries)

    def fake_prepare_review(**kwargs):
        output_path = kwargs["output_path"]
        output_path.write_text(json.dumps({"review_id": "review-123", "items": []}))
        items = [
            FakeReviewItem(
                flight_id="flight-1",
                started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
                duration_seconds=3600,
                tail_number=None,
                metadata={"origin": "KSEA", "destination": "KLAX"},
                status="ok",
                message=None,
            )
        ]
        return items, "review-123"

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", fake_build_cloudahoy)
    monkeypatch.setattr(service_mod, "prepare_review", fake_prepare_review)

    payload = JobCreateRequest(credentials=_credentials())
    result = job_service.generate_review(job.job_id, payload)

    assert result.status == "review_ready"
    assert result.review_summary is not None
    assert result.review_summary.flight_count == 1

    summary_path = job_service._store.job_dir(job.job_id) / "review-summary.json"
    assert summary_path.exists()


def test_generate_review_failure_marks_job_failed(job_service: JobService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Generate review should set job failed when prepare_review raises."""
    job = job_service.create_job("pilot")

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", lambda *args, **kwargs: FakeCloudAhoy([]))
    monkeypatch.setattr(service_mod, "prepare_review", lambda **kwargs: (_ for _ in ()).throw(ValueError("boom")))

    payload = JobCreateRequest(credentials=_credentials())
    result = job_service.generate_review(job.job_id, payload)

    assert result.status == "failed"
    assert result.error_message is not None
    assert "Review failed" in result.error_message


def test_generate_review_reports_incremental_progress(
    job_service: JobService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Generate review should emit per-flight review progress while building artifacts."""
    job = job_service.create_job("pilot")

    summaries = [
        CoreFlightSummary(
            id="flight-1",
            started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            aircraft_type="C172",
            tail_number="N123",
        ),
        CoreFlightSummary(
            id="flight-2",
            started_at=datetime(2026, 1, 6, 9, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
            aircraft_type="C172",
            tail_number="N124",
        ),
    ]

    def fake_build_cloudahoy(payload, exports_dir: Path):
        exports_dir.mkdir(parents=True, exist_ok=True)
        return FakeCloudAhoy(summaries)

    def fake_prepare_review(**kwargs):
        progress = kwargs["progress"]
        for index, summary in enumerate(summaries, start=1):
            progress(index, len(summaries), summary)
        output_path = kwargs["output_path"]
        output_path.write_text(json.dumps({"review_id": "review-123", "items": []}))
        items = [
            FakeReviewItem(
                flight_id="flight-1",
                started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
                duration_seconds=3600,
                tail_number="N123",
                metadata={},
                status="ok",
                message=None,
            ),
            FakeReviewItem(
                flight_id="flight-2",
                started_at=datetime(2026, 1, 6, 9, 0, tzinfo=timezone.utc),
                duration_seconds=1800,
                tail_number="N124",
                metadata={},
                status="ok",
                message=None,
            ),
        ]
        return items, "review-123"

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", fake_build_cloudahoy)
    monkeypatch.setattr(service_mod, "prepare_review", fake_prepare_review)

    payload = JobCreateRequest(credentials=_credentials())
    result = job_service.generate_review(job.job_id, payload)

    assert result.status == "review_ready"
    stored = job_service._store.load_job(job.job_id)
    assert any(event.stage == "Preparing review (1/2)" for event in stored.progress_log)
    assert stored.review_summary is not None


def test_accept_review_missing_review_manifest(job_service: JobService) -> None:
    """Accept review should fail when review manifest is missing."""
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job_service._store.save_job(job)

    payload = JobAcceptRequest(credentials=_credentials())
    result = job_service.accept_review(job.job_id, payload)

    assert result.status == "failed"
    assert result.error_message is not None
    assert "Review manifest missing" in result.error_message


def test_accept_review_success(job_service: JobService, monkeypatch: pytest.MonkeyPatch) -> None:
    """Accept review should produce import report after finalization."""
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job_service._store.save_job(job)

    job_dir = job_service._store.job_dir(job.job_id)
    review_payload = {
        "review_id": "review-123",
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T09:00:00Z",
                "duration_seconds": 3600,
                "tail_number": "N123",
            }
        ],
    }
    (job_dir / "review.json").write_text(json.dumps(review_payload))

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", lambda *args, **kwargs: FakeCloudAhoy([]))
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda *args, **kwargs: FakeFlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    def fake_migrate_flights(**kwargs):
        report_path = kwargs["report_path"]
        report_path.write_text(json.dumps({"results": []}))
        results = [
            MigrationResult(flight_id="flight-1", status="ok"),
            MigrationResult(flight_id="flight-2", status="skipped"),
            MigrationResult(flight_id="flight-3", status="error"),
        ]
        return results, {}

    monkeypatch.setattr(service_mod, "migrate_flights", fake_migrate_flights)

    payload = JobAcceptRequest(credentials=_credentials())
    result = job_service.accept_review(job.job_id, payload)

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 1
    assert result.import_report.skipped_count == 1
    assert result.import_report.failed_count == 1
