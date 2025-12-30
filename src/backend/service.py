from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from src.cloudahoy.client import CloudAhoyClient
from src.migration import prepare_review, migrate_flights
from src.models import FlightSummary as CoreFlightSummary
from src.state import MigrationState
from src.flysto.client import FlyStoClient

from .models import ImportReport, JobAcceptRequest, JobCreateRequest, JobRecord, ReviewSummary, FlightSummary
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

    def generate_review(self, job_id: UUID, payload: JobCreateRequest) -> JobRecord:
        job = self._store.load_job(job_id)
        job.status = "review_running"
        job.updated_at = _now()
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

            items, review_id = prepare_review(
                cloudahoy=cloudahoy,
                summaries=summaries,
                max_flights=payload.max_flights,
                state=state,
                force=False,
                output_path=review_path,
            )

            review_summary = _build_review_summary(items)
            job.review_id = review_id
            job.review_summary = review_summary
            job.status = "review_ready"
            job.updated_at = _now()
            job.error_message = None
            self._store.save_job(job)
            self._store.write_artifact(job_id, "review-summary.json", review_summary.model_dump())
            return job
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Review failed: {exc}"
            job.updated_at = _now()
            self._store.save_job(job)
            return job

    def accept_review(self, job_id: UUID, payload: JobAcceptRequest) -> JobRecord:
        job = self._store.load_job(job_id)
        job.status = "import_running"
        job.updated_at = _now()
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
                progress=None,
            )

            imported_count = sum(1 for result in results if result.status == "ok")
            skipped_count = sum(1 for result in results if result.status == "skipped")
            failed_count = sum(1 for result in results if result.status == "error")

            report = ImportReport(
                imported_count=imported_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
            )
            job.import_report = report
            job.status = "completed"
            job.updated_at = _now()
            job.error_message = None
            self._store.save_job(job)
            return job
        except Exception as exc:
            job.status = "failed"
            job.error_message = f"Import failed: {exc}"
            job.updated_at = _now()
            self._store.save_job(job)
            return job


def _build_cloudahoy_client(payload: JobCreateRequest | JobAcceptRequest, exports_dir: Path) -> CloudAhoyClient:
    exports_dir.mkdir(parents=True, exist_ok=True)
    export_format = _env("CLOUD_AHOY_EXPORT_FORMAT") or "g3x"
    export_formats = _parse_export_formats(_env("CLOUD_AHOY_EXPORT_FORMATS") or export_format)
    return CloudAhoyClient(
        api_key=_env("CLOUD_AHOY_API_KEY"),
        base_url=_env("CLOUD_AHOY_BASE_URL") or "https://www.cloudahoy.com/api",
        email=payload.credentials.cloudahoy_username,
        password=payload.credentials.cloudahoy_password,
        exports_dir=exports_dir,
        export_format=export_format,
        export_formats=export_formats,
    )


def _build_flysto_client(payload: JobAcceptRequest) -> FlyStoClient:
    include_metadata = _bool_env("FLYSTO_INCLUDE_METADATA", False)
    min_request_interval = _float_env("FLYSTO_MIN_REQUEST_INTERVAL", 0.1)
    max_request_retries = _int_env("FLYSTO_MAX_REQUEST_RETRIES", 2)
    return FlyStoClient(
        api_key=_env("FLYSTO_API_KEY") or "",
        base_url=_env("FLYSTO_BASE_URL") or "https://www.flysto.net",
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
    if not start_date and not end_date:
        return None
    summaries = cloudahoy.list_flights(limit=max_flights)
    start_bound = _parse_date_bound(start_date, is_end=False) if start_date else None
    end_bound = _parse_date_bound(end_date, is_end=True) if end_date else None
    filtered = _filter_summaries_by_date(summaries, start_bound, end_bound)
    return filtered[:max_flights] if max_flights else filtered


def _summaries_from_review(payload: dict) -> list[CoreFlightSummary]:
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
                origin=item.metadata.get("origin") if isinstance(item.metadata, dict) else None,
                destination=item.metadata.get("destination") if isinstance(item.metadata, dict) else None,
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


def _parse_date_bound(value: str, is_end: bool) -> datetime:
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
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _bool_env(name: str, default: bool) -> bool:
    value = _env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def _float_env(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _now() -> datetime:
    return datetime.now(timezone.utc)
