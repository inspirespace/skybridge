"""Job orchestration for review/import flows.

This module bridges the core migration logic (`src/core/`) with the backend
job model, persisting progress and artifacts via JobStore.
"""
from __future__ import annotations

import json
import os
import time
import tempfile
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import UUID, uuid4

from src.core.cloudahoy.client import CloudAhoyClient
from src.core.migration import (
    _build_import_tags,
    _build_report_item,
    _extract_crew_assignments,
    _extract_metadata,
    _hash_file,
    _migrate_single,
    _normalize_remarks,
    migrate_flights,
    prepare_review,
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
    CredentialPayload,
)
from .store import JobStore

REVIEW_MANIFEST_ARTIFACT = "review.json"
REVIEW_FLIGHTS_ARTIFACT = "review-flights.json"
IMPORT_REPORT_ARTIFACT = "import-report.json"
IMPORT_CONTEXT_ARTIFACT = "import-context.json"


class JobService:
    """Coordinates job lifecycle transitions and persists progress."""
    def __init__(self, store: JobStore) -> None:
        """Internal helper for init  ."""
        self._store = store

    def _materialize_json_artifact(self, job_id: UUID, artifact_name: str, target_path: Path) -> bool:
        """Restore a JSON artifact onto local disk when needed."""
        if target_path.exists():
            return True
        try:
            payload = self._store.load_artifact(job_id, artifact_name)
        except FileNotFoundError:
            return False
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(payload, indent=2))
        return True

    def create_job(self, user_id: str) -> JobRecord:
        """Create job."""
        job = JobRecord(
            job_id=uuid4(),
            user_id=user_id,
            status="review_running",
            created_at=_now(),
            updated_at=_now(),
            heartbeat_at=_now(),
        )
        _append_progress(job, phase="review", stage="Queued", percent=5, status="review_running")
        self._store.save_job(job)
        return job

    def generate_review(self, job_id: UUID, payload: JobCreateRequest) -> JobRecord:
        """Handle generate review."""
        job = self._store.load_job(job_id)
        try:
            job_dir = self._store.job_dir(job_id)
            work_dir = job_dir / "work"
            exports_dir = work_dir / "cloudahoy_exports"
            state_path = job_dir / "migration.db"
            self._store.materialize_artifact_file(job_id, "migration.db", state_path)
            cloudahoy = _build_cloudahoy_client(payload, exports_dir)
            state = MigrationState(state_path)
            batch_size = max(1, _int_env("BACKEND_REVIEW_BATCH_SIZE", 5))

            job.status = "review_running"
            job.error_message = None
            _touch_heartbeat(job)
            if job.phase_total is None or job.phase_cursor is None:
                _append_progress(
                    job,
                    phase="review",
                    stage="Fetching CloudAhoy flights",
                    percent=10,
                    status="review_running",
                )
                self._store.save_job(job)
                summaries = _summaries_for_range(
                    cloudahoy,
                    payload.start_date,
                    payload.end_date,
                    payload.max_flights,
                )
                if summaries is None:
                    summaries = cloudahoy.list_flights(limit=payload.max_flights)
                manifest_items = [_summary_manifest_item(summary) for summary in summaries]
                review_id = _compute_manifest_review_id(manifest_items)
                review_payload = {
                    "generated_at": _now().isoformat().replace("+00:00", "Z"),
                    "review_id": review_id,
                    "count": len(manifest_items),
                    "items": manifest_items,
                }
                self._store.write_artifact(job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)
                self._store.write_artifact(
                    job_id,
                    REVIEW_FLIGHTS_ARTIFACT,
                    {"review_id": review_id, "count": len(manifest_items), "items": []},
                )
                job.review_id = review_id
                job.phase_cursor = 0
                job.phase_total = len(manifest_items)
                job.review_summary = _build_review_summary_from_rows([])
                self._store.save_job(job)

            review_payload = self._store.load_artifact(job_id, REVIEW_MANIFEST_ARTIFACT)
            flights_payload = _load_json_payload(
                self._store,
                job_id,
                REVIEW_FLIGHTS_ARTIFACT,
                {"review_id": job.review_id, "count": job.phase_total or 0, "items": []},
            )
            manifest_items = review_payload.get("items", [])
            total_summaries = len(manifest_items)
            cursor = min(job.phase_cursor or 0, total_summaries)

            for index in range(cursor, min(cursor + batch_size, total_summaries)):
                item = manifest_items[index]
                summary = _summary_from_manifest_item(item)
                _touch_heartbeat(job, store=self._store)
                percent = 45 + int(((index + 1) / max(total_summaries, 1)) * 35)
                _append_progress(
                    job,
                    phase="review",
                    stage=f"Preparing review ({index + 1}/{total_summaries})",
                    percent=min(max(percent, 45), 80),
                    status="review_running",
                    flight_id=summary.id,
                )
                self._store.save_job(job)

                detail = cloudahoy.fetch_flight(summary.id, file_id=item.get("fd_id"))
                metadata = _extract_metadata(detail.raw_payload)
                row = _build_review_row(summary, metadata)
                flights_payload["review_id"] = job.review_id
                flights_payload["count"] = total_summaries
                flights_payload["items"] = _upsert_by_flight_id(flights_payload.get("items"), row.model_dump())
                item["tail_number"] = metadata.get("tail_number") or item.get("tail_number")
                review_payload["items"] = _upsert_by_flight_id(manifest_items, item)
                manifest_items = review_payload["items"]
                self._store.write_artifact(job_id, REVIEW_FLIGHTS_ARTIFACT, flights_payload)
                self._store.write_artifact(job_id, REVIEW_MANIFEST_ARTIFACT, review_payload)
                _upload_detail_artifacts(self._store, job_id, detail)

                job.phase_cursor = index + 1
                _touch_heartbeat(job)
                self._store.save_job(job)

            if (job.phase_cursor or 0) < total_summaries:
                return job

            _append_progress(
                job,
                phase="review",
                stage="Building summary",
                percent=80,
                status="review_running",
            )
            self._store.save_job(job)

            rows = [
                FlightSummary.model_validate(item)
                for item in flights_payload.get("items", [])
                if isinstance(item, dict)
            ]
            review_summary = _build_review_summary_from_rows(rows)
            job.review_summary = review_summary
            job.status = "review_ready"
            job.phase_cursor = total_summaries
            job.phase_total = total_summaries
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
        try:
            job_dir = self._store.job_dir(job_id)
            work_dir = job_dir / "work"
            exports_dir = work_dir / "cloudahoy_exports"
            review_path = job_dir / REVIEW_MANIFEST_ARTIFACT
            report_path = job_dir / IMPORT_REPORT_ARTIFACT
            context_path = job_dir / IMPORT_CONTEXT_ARTIFACT
            state_path = job_dir / "migration.db"

            try:
                review_payload = self._store.load_artifact(job_id, REVIEW_MANIFEST_ARTIFACT)
            except FileNotFoundError:
                raise FileNotFoundError("Review manifest missing; rerun review")
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(json.dumps(review_payload, indent=2))
            self._store.materialize_artifact_file(job_id, "migration.db", state_path)
            self._materialize_json_artifact(job_id, IMPORT_REPORT_ARTIFACT, report_path)
            self._materialize_json_artifact(job_id, IMPORT_CONTEXT_ARTIFACT, context_path)
            review_id = review_payload.get("review_id")
            summaries = _sort_import_summaries(_summaries_from_review(review_payload))

            cloudahoy = _build_cloudahoy_client(payload, exports_dir)
            flysto = _build_flysto_client(payload)
            state = MigrationState(state_path)
            batch_size = max(1, _int_env("BACKEND_IMPORT_BATCH_SIZE", 3))

            job.status = "import_running"
            job.error_message = None
            _touch_heartbeat(job)
            if job.phase_total is None or job.phase_total != len(summaries):
                job.phase_total = len(summaries)
                if job.phase_cursor is None:
                    job.phase_cursor = 0
            _append_progress(
                job,
                phase="import",
                stage="Uploading flights",
                percent=10,
                status="import_running",
            )
            self._store.save_job(job)
            if not flysto.prepare():
                raise RuntimeError("FlySto login failed: check credentials")

            report_payload = _load_or_create_import_report(report_path, review_id, len(summaries))
            import_context = _load_or_create_import_context(context_path)
            total_summaries = len(summaries)
            start_index = min(job.phase_cursor or 0, total_summaries)
            end_index = min(start_index + batch_size, total_summaries)
            dry_run = _bool_env("DRY_RUN", False)

            for index in range(start_index, end_index):
                summary = summaries[index]
                _touch_heartbeat(job, store=self._store)
                _append_progress(
                    job,
                    phase="import",
                    stage=f"Processing flight {_short_flight_id(summary.id)}",
                    percent=min(70, 10 + int(((index + 1) / max(total_summaries, 1)) * 50)),
                    status="import_running",
                    flight_id=summary.id,
                )
                self._store.save_job(job)

                detail = cloudahoy.fetch_flight(summary.id)
                file_hash = _hash_file(detail.file_path)
                csv_hash = _hash_file(detail.csv_path)
                metadata_hash = _hash_file(detail.metadata_path)
                metadata = _extract_metadata(detail.raw_payload) if not dry_run else {}
                tail_number = metadata.get("tail_number") if isinstance(metadata, dict) else summary.tail_number
                aircraft_type = metadata.get("aircraft_type") if isinstance(metadata, dict) else summary.aircraft_type
                crew = _extract_crew_assignments(metadata) if not dry_run else []
                remarks = _normalize_remarks(metadata.get("remarks")) if metadata else None
                tags = _build_import_tags(f"cloudahoy:{_format_import_tag_value()}")

                aircraft = None
                if tail_number and not dry_run:
                    aircraft = _aircraft_from_context(import_context, tail_number)
                    if aircraft is None:
                        aircraft = flysto.ensure_aircraft(tail_number, aircraft_type)
                        _remember_aircraft(import_context, tail_number, aircraft)

                result = _migrate_single(
                    detail,
                    flysto,
                    dry_run,
                    aircraft=aircraft,
                    crew=crew,
                    remarks=remarks,
                    tags=tags,
                    progress=lambda event, payload_dict: _record_import_progress(
                        self._store,
                        job,
                        total_summaries,
                        event,
                        payload_dict,
                    ),
                )

                if state:
                    state.upsert(
                        summary.id,
                        result.status,
                        result.message,
                        file_hash=file_hash,
                        csv_hash=csv_hash,
                        metadata_hash=metadata_hash,
                    )
                report_item = _build_report_item(
                    detail=detail,
                    status=result.status,
                    message=result.message,
                    tail_number=tail_number,
                    aircraft_type=aircraft_type,
                    started_at=summary.started_at,
                    remarks=remarks,
                    tags=tags,
                    crew=crew,
                    flysto=flysto if not dry_run else None,
                )
                report_payload["items"] = _upsert_by_flight_id(report_payload.get("items"), report_item)
                _recompute_import_report_stats(report_payload)

                if (
                    not dry_run
                    and tail_number
                    and aircraft
                    and aircraft.get("id")
                    and tail_number not in set(import_context.get("assigned_unknown_tails", []))
                    and _tail_group_complete(summaries, index, tail_number)
                ):
                    flysto.assign_aircraft(
                        str(aircraft.get("id")),
                        log_format_id="GenericGpx",
                        system_id=None,
                    )
                    import_context.setdefault("assigned_unknown_tails", []).append(tail_number)

                report_path.write_text(json.dumps(report_payload, indent=2))
                context_path.write_text(json.dumps(import_context, indent=2))
                self._store.write_artifact(job_id, IMPORT_REPORT_ARTIFACT, report_payload)
                self._store.write_artifact(job_id, IMPORT_CONTEXT_ARTIFACT, import_context)
                self._store.upload_artifact(job_id, "migration.db", state_path)

                if result.status == "error":
                    job.status = "failed"
                    _append_progress(
                        job,
                        phase="import",
                        stage="Import failed",
                        percent=job.progress_percent,
                        status="failed",
                        flight_id=summary.id,
                    )
                    job.error_message = result.message or "Import failed"
                    self._store.save_job(job)
                    return job

                job.phase_cursor = index + 1
                _touch_heartbeat(job)
                self._store.save_job(job)

            if (job.phase_cursor or 0) < total_summaries:
                return job

            _append_progress(
                job,
                phase="import",
                stage="Reconciling data",
                percent=70,
                status="import_running",
            )
            self._store.save_job(job)

            if not dry_run:
                _append_progress(
                    job,
                    phase="import",
                    stage="Finalizing import",
                    percent=85,
                    status="import_running",
                )
                self._store.save_job(job)
                _maybe_wait_for_processing(flysto, heartbeat=lambda: _touch_heartbeat(job, store=self._store))
                verify_import_report(report_path, flysto)
                reconcile_aircraft_from_report(report_path, flysto)
                reconcile_crew_from_report(report_path, flysto, review_path, cloudahoy)
                reconcile_metadata_from_report(report_path, flysto)
                # Crew can be cleared by FlySto post-processing; reapply after the queue drains.
                _maybe_wait_for_processing(flysto, heartbeat=lambda: _touch_heartbeat(job, store=self._store))
                reconcile_crew_from_report(report_path, flysto, review_path, cloudahoy)
            final_report_payload = _load_or_create_import_report(report_path, review_id, len(summaries))
            job.import_report = ImportReport(
                imported_count=sum(1 for item in final_report_payload.get("items", []) if item.get("status") == "ok"),
                skipped_count=sum(1 for item in final_report_payload.get("items", []) if item.get("status") == "skipped"),
                failed_count=sum(1 for item in final_report_payload.get("items", []) if item.get("status") == "error"),
            )
            job.status = "completed"
            job.phase_cursor = total_summaries
            job.phase_total = total_summaries
            _append_progress(
                job,
                phase="import",
                stage="Import complete",
                percent=100,
                status="completed",
            )
            job.error_message = None
            self._store.save_job(job)
            self._store.write_artifact(job_id, IMPORT_REPORT_ARTIFACT, final_report_payload)
            self._store.upload_artifact(job_id, "migration.db", state_path)
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
            if "state_path" in locals():
                self._store.upload_artifact(job_id, "migration.db", state_path)
            if "report_path" in locals() and report_path.exists():
                self._store.upload_artifact(job_id, IMPORT_REPORT_ARTIFACT, report_path)
            if "context_path" in locals() and context_path.exists():
                self._store.upload_artifact(job_id, IMPORT_CONTEXT_ARTIFACT, context_path)
            return job


def _summary_manifest_item(summary: CoreFlightSummary) -> dict[str, object]:
    """Create a slim manifest item that is safe to persist in Firestore-backed jobs."""
    return {
        "flight_id": summary.id,
        "started_at": summary.started_at.isoformat() if isinstance(summary.started_at, datetime) else None,
        "duration_seconds": summary.duration_seconds,
        "aircraft_type": summary.aircraft_type,
        "tail_number": summary.tail_number,
        "fd_id": getattr(summary, "fd_id", None),
    }


def _compute_manifest_review_id(items: list[dict[str, object]]) -> str:
    """Compute a stable review id from the slim review manifest."""
    payload = [
        {
            "flight_id": item.get("flight_id"),
            "started_at": item.get("started_at"),
            "duration_seconds": item.get("duration_seconds"),
        }
        for item in items
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _summary_from_manifest_item(item: dict[str, object]) -> CoreFlightSummary:
    """Build a core summary from a slim review manifest item."""
    started_at = None
    raw_started_at = item.get("started_at")
    if isinstance(raw_started_at, str) and raw_started_at:
        try:
            started_at = datetime.fromisoformat(raw_started_at.replace("Z", "+00:00"))
        except ValueError:
            started_at = None
    return CoreFlightSummary(
        id=str(item.get("flight_id") or ""),
        started_at=started_at or _now(),
        duration_seconds=item.get("duration_seconds") if isinstance(item.get("duration_seconds"), int) else None,
        aircraft_type=item.get("aircraft_type") if isinstance(item.get("aircraft_type"), str) else None,
        tail_number=item.get("tail_number") if isinstance(item.get("tail_number"), str) else None,
        fd_id=item.get("fd_id") if isinstance(item.get("fd_id"), str) else None,
    )


def _build_review_row(summary: CoreFlightSummary, metadata: dict | None) -> FlightSummary:
    """Build the UI review row stored in review-flights.json."""
    date_value = summary.started_at.isoformat() if isinstance(summary.started_at, datetime) else ""
    tail_number = None
    if isinstance(metadata, dict):
        tail_number = metadata.get("tail_number")
    return FlightSummary(
        flight_id=summary.id,
        date=date_value,
        tail_number=tail_number or summary.tail_number,
        origin=_flight_origin(metadata),
        destination=_flight_destination(metadata),
        flight_time_minutes=(int(summary.duration_seconds) // 60) if summary.duration_seconds else None,
        status="ready",
        message=None,
    )


def _build_review_summary_from_rows(items: list[FlightSummary]) -> ReviewSummary:
    """Build the lightweight review summary persisted on the job record."""
    total_seconds = 0
    earliest: datetime | None = None
    latest: datetime | None = None
    missing_tail = 0
    for item in items:
        if item.date:
            try:
                started_at = datetime.fromisoformat(item.date.replace("Z", "+00:00"))
            except ValueError:
                started_at = None
            if started_at is not None:
                if earliest is None or started_at < earliest:
                    earliest = started_at
                if latest is None or started_at > latest:
                    latest = started_at
        if item.flight_time_minutes:
            total_seconds += int(item.flight_time_minutes) * 60
        if not item.tail_number:
            missing_tail += 1
    return ReviewSummary(
        flight_count=len(items),
        total_hours=round(total_seconds / 3600.0, 2) if total_seconds else 0.0,
        earliest_date=earliest.isoformat() if earliest else None,
        latest_date=latest.isoformat() if latest else None,
        missing_tail_numbers=missing_tail,
        flights=[],
    )


def _load_json_payload(store: JobStore, job_id: UUID, artifact_name: str, default: dict) -> dict:
    """Load a JSON artifact or return a copy of the provided default."""
    try:
        payload = store.load_artifact(job_id, artifact_name)
        if isinstance(payload, dict):
            return payload
    except FileNotFoundError:
        pass
    return json.loads(json.dumps(default))


def _upsert_by_flight_id(items: object, payload: dict[str, object]) -> list[dict[str, object]]:
    """Replace or append a flight keyed payload while preserving order."""
    rows = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    flight_id = payload.get("flight_id")
    if not isinstance(flight_id, str) or not flight_id:
        return rows
    updated: list[dict[str, object]] = []
    replaced = False
    for item in rows:
        if item.get("flight_id") == flight_id:
            updated.append(payload)
            replaced = True
        else:
            updated.append(item)
    if not replaced:
        updated.append(payload)
    return updated


def _upload_detail_artifacts(store: JobStore, job_id: UUID, detail) -> None:
    """Upload the current review/import artifacts immediately after each flight."""
    for attr in ("file_path", "csv_path", "raw_path", "metadata_path"):
        raw_value = getattr(detail, attr, None)
        if not isinstance(raw_value, str) or not raw_value:
            continue
        path = Path(raw_value)
        if not path.exists():
            continue
        store.upload_artifact_as(job_id, f"cloudahoy_exports/{path.name}", path)
    export_paths = getattr(detail, "export_paths", None)
    if isinstance(export_paths, dict):
        for raw_value in export_paths.values():
            if not isinstance(raw_value, str) or not raw_value:
                continue
            path = Path(raw_value)
            if path.exists():
                store.upload_artifact_as(job_id, f"cloudahoy_exports/{path.name}", path)


def _load_or_create_import_report(report_path: Path, review_id: str | None, attempted: int) -> dict:
    """Load the persisted import report or initialize a new one."""
    if report_path.exists():
        try:
            payload = json.loads(report_path.read_text())
            if isinstance(payload, dict):
                payload.setdefault("review_id", review_id)
                payload.setdefault("attempted", attempted)
                payload.setdefault("items", [])
                return payload
        except json.JSONDecodeError:
            pass
    payload = {
        "review_id": review_id,
        "attempted": attempted,
        "succeeded": 0,
        "failed": 0,
        "items": [],
        "processing_queue": None,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2))
    return payload


def _load_or_create_import_context(context_path: Path) -> dict:
    """Load persisted import context or initialize it."""
    if context_path.exists():
        try:
            payload = json.loads(context_path.read_text())
            if isinstance(payload, dict):
                payload.setdefault("aircraft_by_tail", {})
                payload.setdefault("assigned_unknown_tails", [])
                return payload
        except json.JSONDecodeError:
            pass
    payload = {"aircraft_by_tail": {}, "assigned_unknown_tails": []}
    context_path.parent.mkdir(parents=True, exist_ok=True)
    context_path.write_text(json.dumps(payload, indent=2))
    return payload


def _aircraft_from_context(context: dict, tail_number: str) -> dict | None:
    """Return cached aircraft metadata from persisted import context."""
    aircraft = context.get("aircraft_by_tail", {}).get(tail_number)
    if isinstance(aircraft, dict):
        return aircraft
    return None


def _remember_aircraft(context: dict, tail_number: str, aircraft: dict | None) -> None:
    """Persist aircraft metadata for later import batches."""
    if not isinstance(aircraft, dict):
        return
    context.setdefault("aircraft_by_tail", {})[tail_number] = aircraft


def _record_import_progress(
    store: JobStore,
    job: JobRecord,
    total_summaries: int,
    event: str,
    payload: dict,
) -> None:
    """Translate migrate progress callbacks into job progress events."""
    flight_id = payload.get("flight_id")
    short_id = _short_flight_id(flight_id) if flight_id else None
    if event == "start":
        stage = f"Processing flight {short_id}" if short_id else "Processing flight"
        percent = job.progress_percent
    elif event == "flysto_upload_start":
        stage = f"Uploading flight {short_id}" if short_id else "Uploading flight"
        percent = job.progress_percent
    elif event == "end":
        processed = (job.phase_cursor or 0) + 1
        percent = min(70, 10 + int((processed / max(total_summaries, 1)) * 50))
        stage = f"Processed flight {short_id}" if short_id else "Processed flight"
    else:
        return
    _append_progress(
        job,
        phase="import",
        stage=stage,
        percent=percent,
        status="import_running",
        flight_id=flight_id if isinstance(flight_id, str) else None,
    )
    store.save_job(job)


def _recompute_import_report_stats(payload: dict) -> None:
    """Recompute aggregate import counts from the report item list."""
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    payload["attempted"] = payload.get("attempted") or len(items)
    payload["succeeded"] = sum(1 for item in items if item.get("status") == "ok")
    payload["failed"] = sum(1 for item in items if item.get("status") == "error")


def _tail_group_complete(summaries: list[CoreFlightSummary], index: int, tail_number: str) -> bool:
    """Return True when the current import cursor reached the last summary for a tail."""
    next_index = index + 1
    if next_index >= len(summaries):
        return True
    return summaries[next_index].tail_number != tail_number


def _sort_import_summaries(summaries: list[CoreFlightSummary]) -> list[CoreFlightSummary]:
    """Sort import summaries by tail to keep aircraft assignment resumable."""
    return sorted(
        summaries,
        key=lambda summary: (
            summary.tail_number or "",
            summary.started_at.isoformat() if isinstance(summary.started_at, datetime) else "",
            summary.id,
        ),
    )


def _format_import_tag_value() -> str:
    """Build the import tag timestamp once per migration event."""
    return _now().strftime("%Y-%m-%dT%H:%MZ")


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
    job.heartbeat_at = job.updated_at
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


def _touch_heartbeat(job: JobRecord, *, store: JobStore | None = None) -> None:
    """Refresh the job heartbeat without emitting a new progress event."""
    now = _now()
    job.updated_at = now
    job.heartbeat_at = now
    if store is not None:
        store.save_job(job)


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
        email=payload.credentials.flysto_username,
        password=payload.credentials.flysto_password,
        min_request_interval=min_request_interval,
        max_request_retries=max_request_retries,
    )


def validate_credentials(credentials: CredentialPayload) -> None:
    """Validate CloudAhoy and FlySto credentials."""
    with tempfile.TemporaryDirectory() as temp_dir:
        exports_dir = Path(temp_dir) / "cloudahoy_exports"
        cloudahoy = _build_cloudahoy_client(
            JobCreateRequest(credentials=credentials),
            exports_dir,
        )
        cloudahoy.list_flights(limit=1)

    flysto = _build_flysto_client(JobAcceptRequest(credentials=credentials))
    if not flysto.prepare():
        raise RuntimeError("FlySto login failed: check credentials")


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


def _maybe_wait_for_processing(
    flysto: FlyStoClient,
    heartbeat: Callable[[], None] | None = None,
) -> None:
    """Internal helper for maybe wait for processing."""
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
        if heartbeat is not None:
            heartbeat()
        time.sleep(interval)


def _now() -> datetime:
    """Internal helper for now."""
    return datetime.now(timezone.utc)
