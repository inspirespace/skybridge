from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

from src.cloudahoy.client import CloudAhoyClient
from src.cloudahoy.points import build_points_schema, points_preview
from src.flysto.client import FlyStoClient
from src.models import FlightSummary, MigrationResult
from src.state import MigrationState


@dataclass(frozen=True)
class MigrationStats:
    attempted: int
    succeeded: int
    failed: int


@dataclass(frozen=True)
class ReviewItem:
    flight_id: str
    started_at: datetime
    duration_seconds: int | None
    aircraft_type: str | None
    tail_number: str | None
    status: str
    message: str | None
    file_path: str | None
    file_type: str | None
    points_count: int | None
    points_schema: list[dict]
    points_preview: list[dict]
    has_kml: bool

    def to_dict(self) -> dict:
        return {
            "flight_id": self.flight_id,
            "started_at": self.started_at.isoformat(),
            "duration_seconds": self.duration_seconds,
            "aircraft_type": self.aircraft_type,
            "tail_number": self.tail_number,
            "status": self.status,
            "message": self.message,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "points_count": self.points_count,
            "points_schema": self.points_schema,
            "points_preview": self.points_preview,
            "has_kml": self.has_kml,
        }


def prepare_review(
    cloudahoy: CloudAhoyClient,
    max_flights: int | None = None,
    state: MigrationState | None = None,
    force: bool = False,
    output_path: Path | None = None,
) -> list[ReviewItem]:
    summaries = cloudahoy.list_flights(limit=max_flights)
    items: list[ReviewItem] = []

    for summary in summaries:
        if state and not force:
            record = state.get(summary.id)
            if record and record.status == "ok":
                items.append(
                    _review_item(
                        summary,
                        status="skipped",
                        message="already migrated",
                        file_path=None,
                        file_type=None,
                        points_count=None,
                        points_schema=[],
                        points_preview=[],
                        has_kml=False,
                    )
                )
                continue

        detail = cloudahoy.fetch_flight(summary.id)
        points_count, has_kml, schema, preview = _describe_detail(
            detail.raw_payload, detail.file_path
        )
        items.append(
            _review_item(
                summary,
                status="ready",
                message=None,
                file_path=detail.file_path,
                file_type=detail.file_type,
                points_count=points_count,
                points_schema=schema,
                points_preview=preview,
                has_kml=has_kml,
            )
        )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "count": len(items),
            "summary": _summarize_review(items),
            "items": [item.to_dict() for item in items],
        }
        output_path.write_text(json.dumps(payload, indent=2))

    _cleanup_exports_dir(cloudahoy, items)

    return items


def _review_item(
    summary: FlightSummary,
    status: str,
    message: str | None,
    file_path: str | None,
    file_type: str | None,
    points_count: int | None,
    points_schema: list[dict],
    points_preview: list[dict],
    has_kml: bool,
) -> ReviewItem:
    return ReviewItem(
        flight_id=summary.id,
        started_at=summary.started_at,
        duration_seconds=summary.duration_seconds,
        aircraft_type=summary.aircraft_type,
        tail_number=summary.tail_number,
        status=status,
        message=message,
        file_path=file_path,
        file_type=file_type,
        points_count=points_count,
        points_schema=points_schema,
        points_preview=points_preview,
        has_kml=has_kml,
    )


def _describe_detail(
    raw_payload: dict, file_path: str | None
) -> tuple[int | None, bool, list[dict], list[dict]]:
    flt = raw_payload.get("flt") if isinstance(raw_payload, dict) else {}
    points = flt.get("points") if isinstance(flt, dict) else None
    points_count = len(points) if isinstance(points, list) else None
    has_kml = bool(file_path) or _payload_has_kml(flt)
    schema = build_points_schema(flt) if isinstance(flt, dict) else []
    preview = (
        points_preview(points, schema) if isinstance(points, list) and schema else []
    )
    return points_count, has_kml, schema, preview


def _summarize_review(items: list[ReviewItem]) -> dict:
    skipped = sum(1 for item in items if item.status == "skipped")
    ready = sum(1 for item in items if item.status == "ready")
    return {
        "ready": ready,
        "skipped": skipped,
    }


def _cleanup_exports_dir(cloudahoy: CloudAhoyClient, items: list[ReviewItem]) -> None:
    exports_dir = getattr(cloudahoy, "exports_dir", None)
    if not isinstance(exports_dir, Path):
        return
    if not exports_dir.exists():
        return
    keep = {
        Path(item.file_path).resolve()
        for item in items
        if item.file_path
    }
    for entry in exports_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.resolve() in keep:
            continue
        entry.unlink()


def _payload_has_kml(flt: dict | None) -> bool:
    if not isinstance(flt, dict):
        return False
    kml = flt.get("KML")
    if isinstance(kml, str):
        return kml.lstrip().startswith("<?xml")
    if isinstance(kml, dict):
        return any(
            isinstance(value, str) and value.lstrip().startswith("<?xml")
            for value in kml.values()
        )
    return False


def migrate_flights(
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    dry_run: bool = False,
    max_flights: int | None = None,
    state: MigrationState | None = None,
    force: bool = False,
) -> tuple[list[MigrationResult], MigrationStats]:
    summaries = cloudahoy.list_flights(limit=max_flights)
    results: list[MigrationResult] = []
    succeeded = 0
    failed = 0

    for summary in summaries:
        if state and not force:
            record = state.get(summary.id)
            if record and record.status == "ok":
                results.append(
                    MigrationResult(
                        flight_id=summary.id,
                        status="skipped",
                        message="already migrated",
                    )
                )
                continue
        result = _migrate_single(summary, cloudahoy, flysto, dry_run)
        results.append(result)
        if result.status == "ok":
            succeeded += 1
        else:
            failed += 1

        if state:
            state.upsert(summary.id, result.status, result.message)

    return results, MigrationStats(
        attempted=len(summaries),
        succeeded=succeeded,
        failed=failed,
    )


def _migrate_single(
    summary: FlightSummary,
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    dry_run: bool,
) -> MigrationResult:
    try:
        detail = cloudahoy.fetch_flight(summary.id)
        flysto.upload_flight(detail, dry_run=dry_run)
        return MigrationResult(flight_id=summary.id, status="ok")
    except Exception as exc:  # noqa: BLE001 - surfacing per-flight failure
        return MigrationResult(
            flight_id=summary.id,
            status="error",
            message=str(exc),
        )
