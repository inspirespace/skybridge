"""Job orchestration for review/import flows.

This module bridges the core migration logic (`src/core/`) with the backend
job model, persisting progress and artifacts via JobStore.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from src.core.cloudahoy.client import CloudAhoyClient
from src.core.migration import (
    prepare_review,
    migrate_flights,
    verify_import_report,
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
)
from src.core.models import FlightSummary as CoreFlightSummary
from src.core.state import MigrationState
from src.core.flysto.client import FlyStoClient

from .models import (
    ImportReport,
    JobAcceptRequest,
    JobCreateRequest,
    JobRecord,
    ProgressEvent,
    ReviewSummary,
    FlightSummary,
)
from .store import JobStore


class JobService:
    """Coordinates job lifecycle transitions and persists progress."""
    def __init__(self, store: JobStore) -> None:
        """Internal helper for init  ."""
        self._store = store

    def create_job(self, user_id: str) -> JobRecord:
        """Create job."""
        job = JobRecord(
            job_id=uuid4(),
            user_id=user_id,
            status="review_running",
            created_at=_now(),
            updated_at=_now(),
        )
        _append_progress(job, phase="review", stage="Queued", percent=5, status="review_running")
        self._store.save_job(job)
        return job

    def generate_review(self, job_id: UUID, payload: JobCreateRequest) -> JobRecord:
        """Handle generate review."""
        job = self._store.load_job(job_id)
        job.status = "review_running"
        _append_progress(
            job,
            phase="review",
            stage="Fetching CloudAhoy flights",
            percent=10,
            status="review_running",
        )
        job.error_message = None
        self._store.save_job(job)

        try:
            job_dir = self._store.job_dir(job_id)
            work_dir = job_dir / "work"
            exports_dir = work_dir / "cloudahoy_exports"
            review_path = job_dir / "review.json"
            state_path = job_dir / "migration.db"

            cloudahoy = _build_cloudahoy_client(payload, exports_dir)
            state = MigrationState(state_path)

            summaries = _summaries_for_range(
                cloudahoy,
                payload.start_date,
                payload.end_date,
                payload.max_flights,
            )
            _append_progress(
                job,
                phase="review",
                stage="Preparing review",
                percent=45,
                status="review_running",
            )
            self._store.save_job(job)

            items, review_id = prepare_review(
                cloudahoy=cloudahoy,
                summaries=summaries,
                max_flights=payload.max_flights,
                state=state,
                force=False,
                output_path=review_path,
            )
            _append_progress(
                job,
                phase="review",
                stage="Building summary",
                percent=80,
                status="review_running",
            )
            self._store.save_job(job)

            review_summary = _build_review_summary(items)
            job.review_id = review_id
            job.review_summary = review_summary
            job.status = "review_ready"
            _append_progress(
                job,
                phase="review",
                stage="Review ready",
                percent=100,
                status="review_ready",
            )
            job.error_message = None
            self._store.save_job(job)
            self._store.write_artifact(job_id, "review-summary.json", review_summary.model_dump())
            self._store.upload_artifact(job_id, "review.json", review_path)
            self._store.upload_artifact_dir(
                job_id,
                prefix="cloudahoy_exports",
                directory=exports_dir,
            )
            return job
        except Exception as exc:
            job.status = "failed"
            _append_progress(
                job,
                phase="review",
                stage="Review failed",
                percent=job.progress_percent,
                status="failed",
            )
            job.error_message = f"Review failed: {exc}"
            self._store.save_job(job)
            return job

    def accept_review(self, job_id: UUID, payload: JobAcceptRequest) -> JobRecord:
        """Handle accept review."""
        job = self._store.load_job(job_id)
        job.status = "import_running"
        _append_progress(
            job,
            phase="import",
            stage="Uploading flights",
            percent=10,
            status="import_running",
        )
        job.error_message = None
        self._store.save_job(job)

        try:
            job_dir = self._store.job_dir(job_id)
            work_dir = job_dir / "work"
            exports_dir = work_dir / "cloudahoy_exports"
            review_path = job_dir / "review.json"
            report_path = job_dir / "import-report.json"
            state_path = job_dir / "migration.db"

            if not review_path.exists():
                raise FileNotFoundError("Review manifest missing; rerun review")

            review_payload = json.loads(review_path.read_text())
            review_id = review_payload.get("review_id")
            summaries = _summaries_from_review(review_payload)

            cloudahoy = _build_cloudahoy_client(payload, exports_dir)
            flysto = _build_flysto_client(payload)
            state = MigrationState(state_path)

            if not flysto.prepare():
                raise RuntimeError("FlySto API unavailable; check credentials")

            total_summaries = len(summaries)
            processed = 0

            def progress(event: str, payload: dict) -> None:
                """Handle progress."""
                nonlocal processed
                flight_id = payload.get("flight_id")
                short_id = _short_flight_id(flight_id) if flight_id else None
                if event == "start":
                    _append_progress(
                        job,
                        phase="import",
                        stage=f"Processing flight {short_id}" if short_id else "Processing flight",
                        percent=job.progress_percent,
                        status="import_running",
                        flight_id=flight_id,
                    )
                    self._store.save_job(job)
                elif event == "end":
                    processed += 1
                    if total_summaries:
                        percent = 10 + int((processed / total_summaries) * 50)
                        percent = min(percent, 70)
                    else:
                        percent = job.progress_percent
                    _append_progress(
                        job,
                        phase="import",
                        stage=f"Processed flight {short_id}" if short_id else "Processed flight",
                        percent=percent,
                        status="import_running",
                        flight_id=flight_id,
                    )
                    self._store.save_job(job)
                elif event == "flysto_upload_start":
                    _append_progress(
                        job,
                        phase="import",
                        stage=f"Uploading flight {short_id}" if short_id else "Uploading flight",
                        percent=job.progress_percent,
                        status="import_running",
                        flight_id=flight_id,
                    )
                    self._store.save_job(job)

            results, _stats = migrate_flights(
                cloudahoy=cloudahoy,
                flysto=flysto,
                dry_run=_bool_env("DRY_RUN", False),
                summaries=summaries,
                max_flights=None,
                state=state,
                force=False,
                report_path=report_path,
                review_id=review_id,
                progress=progress,
            )
            _append_progress(
                job,
                phase="import",
                stage="Reconciling data",
                percent=70,
                status="import_running",
            )
            self._store.save_job(job)

            imported_count = sum(1 for result in results if result.status == "ok")
            skipped_count = sum(1 for result in results if result.status == "skipped")
            failed_count = sum(1 for result in results if result.status == "error")

            report = ImportReport(
                imported_count=imported_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
            )

            if _bool_env("BACKEND_RECONCILE", True) and not _bool_env("DRY_RUN", False):
                _append_progress(
                    job,
                    phase="import",
                    stage="Finalizing import",
                    percent=85,
                    status="import_running",
                )
                self._store.save_job(job)
                _maybe_wait_for_processing(flysto)
                verify_import_report(report_path, flysto)
                reconcile_aircraft_from_report(report_path, flysto)
                reconcile_crew_from_report(report_path, flysto, review_path, cloudahoy)
                reconcile_metadata_from_report(report_path, flysto)
                # Crew can be cleared by FlySto post-processing; reapply after the queue drains.
                _maybe_wait_for_processing(flysto)
                reconcile_crew_from_report(report_path, flysto, review_path, cloudahoy)
            job.import_report = report
            job.status = "completed"
            _append_progress(
                job,
                phase="import",
                stage="Import complete",
                percent=100,
                status="completed",
            )
            job.error_message = None
            self._store.save_job(job)
            self._store.upload_artifact(job_id, "import-report.json", report_path)
            return job
        except Exception as exc:
            job.status = "failed"
            _append_progress(
                job,
                phase="import",
                stage="Import failed",
                percent=job.progress_percent,
                status="failed",
            )
            job.error_message = f"Import failed: {exc}"
            self._store.save_job(job)
            return job


def _append_progress(
    job: JobRecord,
    *,
    phase: str,
    stage: str,
    percent: int | None,
    status: str,
    flight_id: str | None = None,
) -> None:
    """Internal helper for append progress."""
    job.progress_stage = stage
    job.progress_percent = percent
    job.updated_at = _now()
    job.progress_log.append(
        ProgressEvent(
            phase=phase,
            stage=stage,
            flight_id=flight_id,
            percent=percent,
            status=status,
            created_at=job.updated_at,
        )
    )
    if len(job.progress_log) > 200:
        job.progress_log = job.progress_log[-200:]


def _short_flight_id(flight_id: str) -> str:
    """Internal helper for short flight id."""
    if len(flight_id) <= 12:
        return flight_id
    return f"...{flight_id[-8:]}"


def _build_cloudahoy_client(payload: JobCreateRequest | JobAcceptRequest, exports_dir: Path) -> CloudAhoyClient:
    """Internal helper for build cloudahoy client."""
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_format = _env("CLOUD_AHOY_EXPORT_FORMAT") or "g3x"
    export_formats = _parse_export_formats(_env("CLOUD_AHOY_EXPORT_FORMATS") or export_format)
    return CloudAhoyClient(
        api_key=_env("CLOUD_AHOY_API_KEY"),
        base_url=_cloudahoy_base_url(),
        email=payload.credentials.cloudahoy_username,
        password=payload.credentials.cloudahoy_password,
        exports_dir=exports_dir,
        export_format=export_format,
        export_formats=export_formats,
    )


def _build_flysto_client(payload: JobAcceptRequest) -> FlyStoClient:
    """Internal helper for build flysto client."""
    include_metadata = _bool_env("FLYSTO_INCLUDE_METADATA", False)
    min_request_interval = _float_env("FLYSTO_MIN_REQUEST_INTERVAL", 0.01)
    max_request_retries = _int_env("FLYSTO_MAX_REQUEST_RETRIES", 2)
    return FlyStoClient(
        api_key=_env("FLYSTO_API_KEY") or "",
        base_url=_flysto_base_url(),
        upload_url=_env("FLYSTO_LOG_UPLOAD_URL"),
        session_cookie=_env("FLYSTO_SESSION_COOKIE"),
        include_metadata=include_metadata,
        api_version=_env("FLYSTO_API_VERSION"),
        email=payload.credentials.flysto_username,
        password=payload.credentials.flysto_password,
        min_request_interval=min_request_interval,
        max_request_retries=max_request_retries,
    )


def _summaries_for_range(
    cloudahoy: CloudAhoyClient,
    start_date: str | None,
    end_date: str | None,
    max_flights: int | None,
) -> list[CoreFlightSummary] | None:
    """Internal helper for summaries for range."""
    if not start_date and not end_date:
        return None
    summaries = cloudahoy.list_flights(limit=max_flights)
    start_bound = _parse_date_bound(start_date, is_end=False) if start_date else None
    end_bound = _parse_date_bound(end_date, is_end=True) if end_date else None
    filtered = _filter_summaries_by_date(summaries, start_bound, end_bound)
    return filtered[:max_flights] if max_flights else filtered


def _summaries_from_review(payload: dict) -> list[CoreFlightSummary]:
    """Internal helper for summaries from review."""
    items = payload.get("items", [])
    summaries: list[CoreFlightSummary] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        flight_id = item.get("flight_id")
        if not isinstance(flight_id, str) or not flight_id:
            continue
        started_at = None
        started_raw = item.get("started_at")
        if isinstance(started_raw, str) and started_raw:
            try:
                normalized = started_raw.replace("Z", "+00:00")
                started_at = datetime.fromisoformat(normalized)
            except ValueError:
                started_at = None
        summaries.append(
            CoreFlightSummary(
                id=flight_id,
                started_at=started_at,
                duration_seconds=item.get("duration_seconds"),
                aircraft_type=item.get("aircraft_type"),
                tail_number=item.get("tail_number"),
            )
        )
    return summaries


def _build_review_summary(items: list) -> ReviewSummary:
    """Internal helper for build review summary."""
    flights: list[FlightSummary] = []
    total_seconds = 0
    earliest: datetime | None = None
    latest: datetime | None = None
    missing_tail = 0

    for item in items:
        started_at = item.started_at
        if isinstance(started_at, datetime):
            if earliest is None or started_at < earliest:
                earliest = started_at
            if latest is None or started_at > latest:
                latest = started_at
        if item.duration_seconds:
            total_seconds += int(item.duration_seconds)
        if not item.tail_number:
            missing_tail += 1

        date_value = ""
        if isinstance(started_at, datetime):
            date_value = started_at.isoformat()
        flights.append(
            FlightSummary(
                flight_id=item.flight_id,
                date=date_value,
                tail_number=item.tail_number,
                origin=_flight_origin(item.metadata),
                destination=_flight_destination(item.metadata),
                flight_time_minutes=(int(item.duration_seconds) // 60) if item.duration_seconds else None,
                status=item.status,
                message=item.message,
            )
        )

    total_hours = round(total_seconds / 3600.0, 2) if total_seconds else 0.0
    earliest_str = earliest.isoformat() if isinstance(earliest, datetime) else None
    latest_str = latest.isoformat() if isinstance(latest, datetime) else None

    return ReviewSummary(
        flight_count=len(flights),
        total_hours=total_hours,
        earliest_date=earliest_str,
        latest_date=latest_str,
        missing_tail_numbers=missing_tail,
        flights=flights,
    )


def _flight_origin(metadata: dict | None) -> str | None:
    """Internal helper for flight origin."""
    if not isinstance(metadata, dict):
        return None
    return _coerce_location(
        metadata.get("origin")
        or metadata.get("aircraft_from")
        or metadata.get("event_from")
        or metadata.get("from")
    )


def _flight_destination(metadata: dict | None) -> str | None:
    """Internal helper for flight destination."""
    if not isinstance(metadata, dict):
        return None
    return _coerce_location(
        metadata.get("destination")
        or metadata.get("aircraft_to")
        or metadata.get("event_to")
        or metadata.get("to")
    )


def _coerce_location(value: object) -> str | None:
    """Internal helper for coerce location."""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        code = value.get("c")
        name = value.get("t")
        if isinstance(code, str) and code:
            return code
        if isinstance(name, str) and name:
            return name
    return None


def _parse_date_bound(value: str, is_end: bool) -> datetime:
    """Internal helper for parse date bound."""
    raw = value.strip()
    normalized = raw.replace("Z", "+00:00")
    if "T" not in normalized and len(normalized) == 10:
        dt = datetime.fromisoformat(normalized)
        if is_end:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _filter_summaries_by_date(
    summaries: list[CoreFlightSummary],
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[CoreFlightSummary]:
    """Internal helper for filter summaries by date."""
    if not start_date and not end_date:
        return summaries
    filtered: list[CoreFlightSummary] = []
    for summary in summaries:
        started_at = summary.started_at
        if started_at is None:
            continue
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if start_date and started_at < start_date:
            continue
        if end_date and started_at > end_date:
            continue
        filtered.append(summary)
    return filtered


def _parse_export_formats(value: str | None) -> list[str]:
    """Internal helper for parse export formats."""
    if not value:
        return ["g3x", "gpx"]
    raw = [part.strip().lower() for part in value.replace(";", ",").split(",")]
    raw = [part for part in raw if part]
    mapped = ["gpx" if part == "cloudahoy" else part for part in raw]
    seen: set[str] = set()
    formats: list[str] = []
    for part in mapped:
        if part in seen:
            continue
        seen.add(part)
        formats.append(part)
    if "gpx" not in formats:
        formats.append("gpx")
    return formats


def _env(name: str) -> str | None:
    """Internal helper for env."""
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _bool_env(name: str, default: bool) -> bool:
    """Internal helper for bool env."""
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    """Internal helper for float env."""
    value = _env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    """Internal helper for int env."""
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _use_mocks() -> bool:
    """Internal helper for use mocks."""
    return _bool_env("DEV_USE_MOCKS", False)


def _cloudahoy_base_url() -> str:
    """Internal helper for cloudahoy base url."""
    if _use_mocks():
        return _env("MOCK_CLOUD_AHOY_BASE_URL") or "http://mock-cloudahoy:8081/api"
    return _env("CLOUD_AHOY_BASE_URL") or "https://www.cloudahoy.com/api"


def _flysto_base_url() -> str:
    """Internal helper for flysto base url."""
    if _use_mocks():
        return _env("MOCK_FLYSTO_BASE_URL") or "http://mock-flysto:8082"
    return _env("FLYSTO_BASE_URL") or "https://www.flysto.net"


def _maybe_wait_for_processing(flysto: FlyStoClient) -> None:
    """Internal helper for maybe wait for processing."""
    if _use_mocks():
        return
    if not _bool_env("BACKEND_WAIT_FOR_PROCESSING", True):
        return
    interval = _float_env("BACKEND_PROCESSING_INTERVAL", 5.0)
    timeout = _float_env("BACKEND_PROCESSING_TIMEOUT", 3600.0)
    start = datetime.now(timezone.utc).timestamp()
    while True:
        try:
            pending = flysto.log_files_to_process()
        except Exception:
            pending = None
        if pending is None or pending <= 0:
            return
        if datetime.now(timezone.utc).timestamp() - start > timeout:
            return
        time.sleep(interval)


def _now() -> datetime:
    """Internal helper for now."""
    return datetime.now(timezone.utc)
