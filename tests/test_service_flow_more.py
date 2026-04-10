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
from src.core.models import FlightDetail, FlightSummary as CoreFlightSummary, MigrationResult


class DummyCloudAhoy:
    def __init__(self, detail: FlightDetail):
        self.detail = detail

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

    def fetch_flight(self, flight_id: str, file_id: str | None = None):
        assert flight_id == "f1"
        return self.detail


class DummyFlySto:
    def __init__(self):
        self.prepare_calls = 0
        self.upload_cache = {}
        self.log_source_cache = {}
        self.aircraft = {}
        self.assigned = []

    def prepare(self) -> bool:
        self.prepare_calls += 1
        return True

    def log_files_to_process(self):
        return 0

    def resolve_log_for_file(self, filename: str, *args, **kwargs):
        return (f"log-{filename}", f"sig-{filename}", "GenericGpx")

    def ensure_aircraft(self, tail_number: str, aircraft_type: str | None = None):
        aircraft = {"id": f"id-{tail_number}", "tail-number": tail_number}
        self.aircraft[tail_number] = aircraft
        return aircraft

    def assign_aircraft(self, aircraft_id: str, log_format_id: str = "GenericGpx", system_id=None):
        self.assigned.append((aircraft_id, log_format_id, system_id))


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

    work_dir = job_dir / "work" / "cloudahoy_exports"
    work_dir.mkdir(parents=True, exist_ok=True)
    file_path = work_dir / "f1.gpx"
    file_path.write_text("gpx-data")
    raw_path = work_dir / "f1.cloudahoy.json"
    raw_payload = {
        "flt": {
            "Meta": {
                "pilot": "Pilot",
                "tailNumber": "N123",
                "from": "KSEA",
                "to": "KLAX",
            }
        }
    }
    raw_path.write_text(json.dumps(raw_payload))
    metadata_path = work_dir / "f1.meta.json"
    metadata_path.write_text(json.dumps({"tail_number": "N123"}))
    detail = FlightDetail(
        id="f1",
        raw_payload=raw_payload,
        raw_path=str(raw_path),
        file_path=str(file_path),
        metadata_path=str(metadata_path),
        csv_path=None,
        export_paths={"gpx": str(file_path)},
    )

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda *_args, **_kwargs: DummyCloudAhoy(detail),
    )
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda *_args, **_kwargs: DummyFlySto())
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 3)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)

    def fake_migrate_single(detail, _flysto, _dry_run, *, progress=None, **_kwargs):
        if progress:
            progress("start", {"flight_id": "f1"})
            progress("flysto_upload_start", {"flight_id": "f1"})
            progress("end", {"flight_id": "f1"})
        return MigrationResult(flight_id=detail.id, status="ok")

    monkeypatch.setattr(service_mod, "_migrate_single", fake_migrate_single)

    payload = JobAcceptRequest(credentials=_credentials())
    result = service.accept_review(job.job_id, payload)
    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 1
