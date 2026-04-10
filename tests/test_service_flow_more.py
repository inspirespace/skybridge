"""Additional JobService flow coverage."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import src.backend.service as service_mod
from src.backend.models import CredentialPayload, JobAcceptRequest
from src.backend.service import JobService
from src.backend.store import JobStore
from src.core.models import FlightSummary as CoreFlightSummary, MigrationResult


class DummyCloudAhoy:
    def list_flights(self, limit=None):
        return [
            CoreFlightSummary(
                id="f1",
                started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                duration_seconds=60,
                aircraft_type=None,
                tail_number=None,
            )
        ]


class DummyFlySto:
    def __init__(self):
        self.prepare_calls = 0

    def prepare(self) -> bool:
        self.prepare_calls += 1
        return True

    def log_files_to_process(self):
        return 0


def _credentials() -> CredentialPayload:
    return CredentialPayload(
        cloudahoy_username="pilot",
        cloudahoy_password="secret",
        flysto_username="pilot",
        flysto_password="secret",
    )


def test_accept_review_progress_and_reconcile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    store = JobStore(tmp_path)
    service = JobService(store)
    job = service.create_job("pilot")
    job.status = "review_ready"
    store.save_job(job)

    job_dir = store.job_dir(job.job_id)
    review_payload = {
        "review_id": "review-1",
        "items": [
            {
                "flight_id": "f1",
                "started_at": "2026-01-01T00:00:00Z",
                "duration_seconds": 60,
            }
        ],
    }
    (job_dir / "review.json").write_text(json.dumps(review_payload))

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", lambda *_args, **_kwargs: DummyCloudAhoy())
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda *_args, **_kwargs: DummyFlySto())
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)

    def fake_migrate_flights(*, progress=None, **_kwargs):
        if progress:
            progress("start", {"flight_id": "f1"})
            progress("flysto_upload_start", {"flight_id": "f1"})
            progress("end", {"flight_id": "f1"})
        return [MigrationResult(flight_id="f1", status="ok")], {}

    monkeypatch.setattr(service_mod, "migrate_flights", fake_migrate_flights)

    payload = JobAcceptRequest(credentials=_credentials())
    result = service.accept_review(job.job_id, payload)
    assert result.status == "completed"
