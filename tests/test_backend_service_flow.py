"""Tests for resumable backend JobService review/import flows."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from src.backend.models import CredentialPayload, JobAcceptRequest, JobCreateRequest
from src.backend.service import (
    IMPORT_CONTEXT_ARTIFACT,
    IMPORT_REPORT_ARTIFACT,
    REVIEW_FLIGHTS_ARTIFACT,
    REVIEW_MANIFEST_ARTIFACT,
    JobService,
)
import src.backend.service as service_mod
from src.backend.store import JobStore
from src.core.flysto.client import UploadResult
from src.core.models import FlightDetail, FlightSummary as CoreFlightSummary


class FakeCloudAhoy:
    def __init__(self, summaries: list[CoreFlightSummary], details: dict[str, FlightDetail]):
        self._summaries = summaries
        self._details = details

    def list_flights(self, limit=None):
        return self._summaries if limit is None else self._summaries[:limit]

    def fetch_flight(self, flight_id: str, file_id: str | None = None):
        return self._details[flight_id]

    def fetch_metadata(self, flight_id: str):
        detail = self._details[flight_id]
        return service_mod._extract_metadata(detail.raw_payload)


class FakeFlySto:
    def __init__(self) -> None:
        self.upload_calls: list[str] = []
        self.ensured: list[str] = []
        self.assigned_unknown: list[str] = []
        self.upload_failures: set[str] = set()

    def prepare(self) -> bool:
        return True

    def ensure_aircraft(self, tail_number: str, aircraft_type: str | None = None):
        self.ensured.append(tail_number)
        return {"id": f"id-{tail_number}", "tail-number": tail_number}

    def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
        self.upload_calls.append(detail.id)
        if detail.id in self.upload_failures:
            self.upload_failures.remove(detail.id)
            raise RuntimeError("transient upload failure")
        return None

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ):
        return None

    def assign_crew_for_log_id(self, log_id: str | None, crew: list[dict]):
        return None

    def assign_metadata_for_log_id(
        self,
        log_id: str | None,
        remarks: str | None = None,
        tags: list[str] | None = None,
    ):
        return None

    def assign_aircraft(self, aircraft_id: str, log_format_id: str = "GenericGpx", system_id=None):
        self.assigned_unknown.append(aircraft_id)

    def resolve_log_for_file(self, filename: str, *args, **kwargs):
        return f"log-{filename}", f"sig-{filename}", "GenericGpx"

    def resolve_log_source_for_log_id(self, log_id: str, *args, **kwargs):
        return "UnknownGarmin", f"source-{log_id}"

    def log_files_to_process(self):
        return 0


class FakeObjectStore:
    def __init__(self) -> None:
        self.json_payloads: dict[str, dict] = {}
        self.files: list[tuple[str, Path]] = []
        self.bytes_payloads: dict[str, bytes] = {}

    def key_for(self, user_id: str, job_id: str, name: str | None = None) -> str:
        if name:
            return f"{user_id}/{job_id}/{name}"
        return f"{user_id}/{job_id}"

    def put_json(self, key: str, payload: dict) -> None:
        self.json_payloads[key] = payload

    def get_json(self, key: str):
        return self.json_payloads.get(key)

    def put_file(self, key: str, path: Path) -> None:
        self.files.append((key, path))

    def get_bytes(self, key: str):
        return self.bytes_payloads.get(key)

    def download_to_file(self, key: str, file_obj) -> bool:
        payload = self.bytes_payloads.get(key)
        if payload is None:
            return False
        file_obj.write(payload)
        return True

    def list_prefix(self, _prefix: str):
        return []

    def delete_prefix(self, _prefix: str):
        return None


@pytest.fixture()
def job_service(tmp_path: Path) -> JobService:
    return JobService(JobStore(tmp_path))


def _credentials() -> CredentialPayload:
    return CredentialPayload(
        cloudahoy_username="pilot",
        cloudahoy_password="secret",
        flysto_username="pilot",
        flysto_password="secret",
    )


def _detail(exports_dir: Path, flight_id: str, started_at: datetime, tail: str, origin: str, destination: str):
    exports_dir.mkdir(parents=True, exist_ok=True)
    file_path = exports_dir / f"{flight_id}.gpx"
    file_path.write_text("gpx-data")
    metadata_path = exports_dir / f"{flight_id}.meta.json"
    metadata_path.write_text(json.dumps({"tail_number": tail}))
    raw_path = exports_dir / f"{flight_id}.cloudahoy.json"
    raw_path.write_text(
        json.dumps(
            {
                "flt": {
                    "Meta": {
                        "tailNumber": tail,
                        "from": origin,
                        "to": destination,
                        "pilot": "Pilot",
                    }
                }
            }
        )
    )
    return FlightDetail(
        id=flight_id,
        raw_payload={
            "flt": {
                "Meta": {
                    "tailNumber": tail,
                    "from": origin,
                    "to": destination,
                    "pilot": "Pilot",
                    "air": 1,
                }
            }
        },
        file_path=str(file_path),
        raw_path=str(raw_path),
        metadata_path=str(metadata_path),
        csv_path=None,
        export_paths={"gpx": str(file_path)},
    )


def test_generate_review_batches_and_writes_slim_artifacts(
    job_service: JobService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    job = job_service.create_job("pilot")
    exports_dir = tmp_path / "exports"
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
            started_at=datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
            aircraft_type="C172",
            tail_number="N124",
        ),
    ]
    details = {
        "flight-1": _detail(exports_dir, "flight-1", summaries[0].started_at, "N123", "KSEA", "KLAX"),
        "flight-2": _detail(exports_dir, "flight-2", summaries[1].started_at, "N124", "KSFO", "KPDX"),
    }

    monkeypatch.setenv("BACKEND_REVIEW_BATCH_SIZE", "1")
    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy(summaries, details),
    )

    payload = JobCreateRequest(credentials=_credentials())
    first = job_service.generate_review(job.job_id, payload)
    assert first.status == "review_running"
    assert first.phase_cursor == 1
    assert first.phase_total == 2

    second = job_service.generate_review(job.job_id, payload)
    assert second.status == "review_ready"
    assert second.phase_cursor == 2
    assert second.review_summary is not None
    assert second.review_summary.flight_count == 2
    assert second.review_summary.flights == []

    review_payload = job_service._store.load_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT)
    assert "points_schema" not in json.dumps(review_payload)
    assert review_payload["items"][0]["flight_id"] == "flight-1"

    review_flights_payload = job_service._store.load_artifact(job.job_id, REVIEW_FLIGHTS_ARTIFACT)
    assert len(review_flights_payload["items"]) == 2
    assert review_flights_payload["items"][0]["origin"] == "KSEA"
    assert review_flights_payload["items"][1]["destination"] == "KPDX"


def test_generate_review_failure_marks_job_failed(
    job_service: JobService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    job = job_service.create_job("pilot")
    summary = CoreFlightSummary(
        id="flight-1",
        started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        aircraft_type="C172",
        tail_number="N123",
    )

    class BrokenCloudAhoy:
        def list_flights(self, limit=None):
            return [summary]

        def fetch_metadata(self, flight_id: str):
            raise RuntimeError("boom")

    monkeypatch.setattr(service_mod, "_build_cloudahoy_client", lambda payload, path: BrokenCloudAhoy())

    result = job_service.generate_review(job.job_id, JobCreateRequest(credentials=_credentials()))
    assert result.status == "failed"
    assert result.error_message is not None
    assert "Review failed" in result.error_message


def test_accept_review_resumes_after_failed_batch_without_reprocessing_prior_flights(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=2, total_hours=1.5, flights=[])
    store.save_job(job)

    review_payload = {
        "review_id": "review-123",
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T09:00:00Z",
                "duration_seconds": 3600,
                "tail_number": "N123",
            },
            {
                "flight_id": "flight-2",
                "started_at": "2026-01-06T10:00:00Z",
                "duration_seconds": 1800,
                "tail_number": "N123",
            },
        ],
    }
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
        "flight-2": _detail(
            exports_dir,
            "flight-2",
            datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            "N123",
            "KSFO",
            "KPDX",
        ),
    }
    flysto = FakeFlySto()
    flysto.upload_failures.add("flight-2")

    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "2")
    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: flysto)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    payload = JobAcceptRequest(credentials=_credentials())
    failed = job_service.accept_review(job.job_id, payload)
    assert failed.status == "failed"
    assert failed.phase_cursor == 1
    assert flysto.upload_calls == ["flight-1", "flight-2"]

    resumed = job_service.accept_review(job.job_id, payload)
    assert resumed.status == "completed"
    assert resumed.phase_cursor == 2
    assert flysto.upload_calls == ["flight-1", "flight-2", "flight-2"]
    assert resumed.import_report is not None
    assert resumed.import_report.imported_count == 2


def test_accept_review_resets_cursor_when_transitioning_from_review_to_import(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "import_queued"
    job.review_summary = service_mod.ReviewSummary(flight_count=2, total_hours=1.5, flights=[])
    job.phase_cursor = 2
    job.phase_total = 2
    job.progress_log = [
        service_mod.ProgressEvent(
            phase="review",
            stage="Review ready",
            percent=100,
            status="review_ready",
            created_at=datetime.now(timezone.utc),
        ),
        service_mod.ProgressEvent(
            phase="import",
            stage="Queued",
            percent=5,
            status="import_queued",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    store.save_job(job)

    review_payload = {
        "review_id": "review-123",
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T09:00:00Z",
                "duration_seconds": 3600,
                "tail_number": "N123",
            },
            {
                "flight_id": "flight-2",
                "started_at": "2026-01-06T10:00:00Z",
                "duration_seconds": 1800,
                "tail_number": "N123",
            },
        ],
    }
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
        "flight-2": _detail(
            exports_dir,
            "flight-2",
            datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            "N123",
            "KSFO",
            "KPDX",
        ),
    }

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "2")
    flysto = FakeFlySto()
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: flysto)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.phase_cursor == 2
    assert result.import_report is not None
    assert result.import_report.imported_count == 2
    assert flysto.upload_calls == ["flight-1", "flight-2"]


def test_accept_review_resets_cursor_after_stale_auto_retry_queue_event(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "import_queued"
    job.review_summary = service_mod.ReviewSummary(flight_count=2, total_hours=1.5, flights=[])
    job.phase_cursor = 2
    job.phase_total = 2
    job.progress_log = [
        service_mod.ProgressEvent(
            phase="review",
            stage="Review ready",
            percent=100,
            status="review_ready",
            created_at=datetime.now(timezone.utc),
        ),
        service_mod.ProgressEvent(
            phase="import",
            stage="Retrying import after worker interruption",
            percent=85,
            status="import_queued",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    store.save_job(job)

    review_payload = {
        "review_id": "review-123",
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T09:00:00Z",
                "duration_seconds": 3600,
                "tail_number": "N123",
            },
            {
                "flight_id": "flight-2",
                "started_at": "2026-01-06T10:00:00Z",
                "duration_seconds": 1800,
                "tail_number": "N123",
            },
        ],
    }
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
        "flight-2": _detail(
            exports_dir,
            "flight-2",
            datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            "N123",
            "KSFO",
            "KPDX",
        ),
    }

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "2")
    flysto = FakeFlySto()
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: flysto)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.phase_cursor == 2
    assert result.import_report is not None
    assert result.import_report.imported_count == 2
    assert flysto.upload_calls == ["flight-1", "flight-2"]


def test_accept_review_loads_manifest_from_object_store_and_persists_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_store = FakeObjectStore()
    store = JobStore(tmp_path, object_store=object_store)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)

    object_store.put_json(
        f"{job.user_id}/{job.job_id}/{REVIEW_MANIFEST_ARTIFACT}",
        {
            "review_id": "review-123",
            "items": [
                {
                    "flight_id": "flight-1",
                    "started_at": "2026-01-05T09:00:00Z",
                    "duration_seconds": 3600,
                    "tail_number": "N123",
                }
            ],
        },
    )

    exports_dir = tmp_path / "exports"
    detail = _detail(
        exports_dir,
        "flight-1",
        datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
        "N123",
        "KSEA",
        "KLAX",
    )
    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], {"flight-1": detail}),
    )
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: FakeFlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))
    assert result.status == "completed"
    assert any(key.endswith("migration.db") for key, _path in object_store.files)

    report_payload = store.load_artifact(job.job_id, IMPORT_REPORT_ARTIFACT)
    assert report_payload["attempted"] == 1
    context_payload = store.load_artifact(job.job_id, IMPORT_CONTEXT_ARTIFACT)
    assert "assigned_unknown_tails" in context_payload


def test_accept_review_preserves_prior_success_when_retry_hits_duplicate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "import_running"
    job.review_summary = service_mod.ReviewSummary(flight_count=2, total_hours=1.5, flights=[])
    job.phase_cursor = 0
    job.phase_total = 2
    job.progress_log = [
        service_mod.ProgressEvent(
            phase="review",
            stage="Review ready",
            percent=100,
            status="review_ready",
            created_at=datetime.now(timezone.utc),
        ),
        service_mod.ProgressEvent(
            phase="import",
            stage="Uploading flights",
            percent=10,
            status="import_running",
            created_at=datetime.now(timezone.utc),
        ),
    ]
    store.save_job(job)

    store.write_artifact(
        job.job_id,
        REVIEW_MANIFEST_ARTIFACT,
        {
            "review_id": "review-123",
            "items": [
                {
                    "flight_id": "flight-1",
                    "started_at": "2026-01-05T09:00:00Z",
                    "duration_seconds": 3600,
                    "tail_number": "N123",
                },
                {
                    "flight_id": "flight-2",
                    "started_at": "2026-01-06T10:00:00Z",
                    "duration_seconds": 1800,
                    "tail_number": "N123",
                },
            ],
        },
    )
    store.write_artifact(
        job.job_id,
        IMPORT_REPORT_ARTIFACT,
        {
            "review_id": "review-123",
            "attempted": 2,
            "succeeded": 1,
            "failed": 0,
            "items": [
                {
                    "flight_id": "flight-1",
                    "status": "ok",
                    "file_path": "flight-1.gpx",
                    "flysto_log_id": "log-flight-1.gpx",
                }
            ],
        },
    )

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
        "flight-2": _detail(
            exports_dir,
            "flight-2",
            datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            "N123",
            "KSFO",
            "KPDX",
        ),
    }

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "2")
    flysto = FakeFlySto()

    def _upload(detail: FlightDetail, dry_run: bool = False):
        flysto.upload_calls.append(detail.id)
        if detail.id == "flight-1":
            raise RuntimeError("Flight already exists")
        return None

    flysto.upload_flight = _upload
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: flysto)
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 2
    payload = store.load_artifact(job.job_id, IMPORT_REPORT_ARTIFACT)
    statuses = {item["flight_id"]: item["status"] for item in payload["items"]}
    assert statuses == {"flight-1": "ok", "flight-2": "ok"}


def test_accept_review_treats_post_upload_assignment_error_as_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=2, total_hours=1.5, flights=[])
    store.save_job(job)

    review_payload = {
        "review_id": "review-123",
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T09:00:00Z",
                "duration_seconds": 3600,
                "tail_number": "N123",
            },
            {
                "flight_id": "flight-2",
                "started_at": "2026-01-06T10:00:00Z",
                "duration_seconds": 1800,
                "tail_number": "N123",
            },
        ],
    }
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
        "flight-2": _detail(
            exports_dir,
            "flight-2",
            datetime(2026, 1, 6, 10, 0, tzinfo=timezone.utc),
            "N123",
            "KSFO",
            "KPDX",
        ),
    }

    class PostUploadFailureFlySto(FakeFlySto):
        def __init__(self) -> None:
            super().__init__()
            self.upload_cache = {}
            self.log_source_cache = {}

        def assign_metadata_for_log_id(
            self,
            log_id: str | None,
            remarks: str | None = None,
            tags: list[str] | None = None,
        ):
            if log_id == "log-flight-2.gpx":
                raise RuntimeError("metadata assignment failed after upload")
            return None

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "2")
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: PostUploadFailureFlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 2
    assert result.import_report.failed_count == 0
    payload = store.load_artifact(job.job_id, IMPORT_REPORT_ARTIFACT)
    statuses = {item["flight_id"]: item["status"] for item in payload["items"]}
    assert statuses == {"flight-1": "ok", "flight-2": "ok"}


def test_accept_review_prefers_upload_log_id_for_metadata_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)

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
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
    }

    class StaleLookupFlySto(FakeFlySto):
        def __init__(self) -> None:
            super().__init__()
            self.upload_cache = {}
            self.log_source_cache = {}

        def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
            self.upload_calls.append(detail.id)
            result = UploadResult(
                signature="flight-1.gpx/hash-new/log-new",
                log_id="log-new",
                log_format="GenericGpx",
                signature_hash="hash-new",
            )
            self.upload_cache[Path(detail.file_path).name] = result
            return result

        def resolve_log_for_file(self, filename: str, *args, **kwargs):
            return "log-old", f"sig-{filename}", "GenericGpx"

        def assign_metadata_for_log_id(
            self,
            log_id: str | None,
            remarks: str | None = None,
            tags: list[str] | None = None,
        ):
            if log_id == "log-old":
                raise RuntimeError("FlySto log-annotations failed: 404 Log not found")
            return None

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "1")
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: StaleLookupFlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 1
    assert result.import_report.failed_count == 0
    payload = store.load_artifact(job.job_id, IMPORT_REPORT_ARTIFACT)
    assert payload["items"][0]["status"] == "ok"


def test_accept_review_tolerates_metadata_404_after_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)

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
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
    }

    class Metadata404FlySto(FakeFlySto):
        def __init__(self) -> None:
            super().__init__()
            self.upload_cache = {}
            self.log_source_cache = {}

        def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
            self.upload_calls.append(detail.id)
            result = UploadResult(
                signature="flight-1.gpx/hash-new/log-new",
                log_id="log-new",
                log_format="GenericGpx",
                signature_hash="hash-new",
            )
            self.upload_cache[Path(detail.file_path).name] = result
            return result

        def assign_metadata_for_log_id(
            self,
            log_id: str | None,
            remarks: str | None = None,
            tags: list[str] | None = None,
        ):
            raise RuntimeError("FlySto log-annotations failed: 404 Log not found")

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "1")
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: Metadata404FlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 1
    assert result.import_report.failed_count == 0


def test_accept_review_tolerates_metadata_503_during_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = JobStore(tmp_path)
    job_service = JobService(store)
    job = job_service.create_job("pilot")
    job.status = "review_ready"
    job.review_summary = service_mod.ReviewSummary(flight_count=1, total_hours=1.0, flights=[])
    store.save_job(job)

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
    store.write_artifact(job.job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)

    exports_dir = tmp_path / "exports"
    details = {
        "flight-1": _detail(
            exports_dir,
            "flight-1",
            datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            "N123",
            "KSEA",
            "KLAX",
        ),
    }

    class Metadata503FlySto(FakeFlySto):
        def __init__(self) -> None:
            super().__init__()
            self.upload_cache = {}
            self.log_source_cache = {}
            self.metadata_attempts = 0

        def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
            self.upload_calls.append(detail.id)
            return UploadResult(
                signature="flight-1.gpx/hash-new/log-new",
                log_id="log-new",
                log_format="GenericGpx",
                signature_hash="hash-new",
            )

        def assign_metadata_for_log_id(
            self,
            log_id: str | None,
            remarks: str | None = None,
            tags: list[str] | None = None,
        ):
            self.metadata_attempts += 1
            raise RuntimeError(
                "FlySto log-annotations failed: 503 <!DOCTYPE html><html><head>"
                "<title>Application Error</title>"
            )

    monkeypatch.setattr(
        service_mod,
        "_build_cloudahoy_client",
        lambda payload, path: FakeCloudAhoy([], details),
    )
    monkeypatch.setenv("BACKEND_IMPORT_BATCH_SIZE", "1")
    monkeypatch.setattr(service_mod, "_build_flysto_client", lambda payload: Metadata503FlySto())
    monkeypatch.setattr(service_mod, "_maybe_wait_for_processing", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service_mod, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(service_mod, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(service_mod, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)

    result = job_service.accept_review(job.job_id, JobAcceptRequest(credentials=_credentials()))

    assert result.status == "completed"
    assert result.import_report is not None
    assert result.import_report.imported_count == 1
    assert result.import_report.failed_count == 0
    payload = store.load_artifact(job.job_id, IMPORT_REPORT_ARTIFACT)
    assert payload["items"][0]["status"] == "ok"
