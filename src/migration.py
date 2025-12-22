from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import string

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
    metadata_path: str | None
    metadata: dict
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
            "metadata_path": self.metadata_path,
            "metadata": self.metadata,
            "has_kml": self.has_kml,
        }


def prepare_review(
    cloudahoy: CloudAhoyClient,
    summaries: list[FlightSummary] | None = None,
    max_flights: int | None = None,
    state: MigrationState | None = None,
    force: bool = False,
    output_path: Path | None = None,
) -> list[ReviewItem]:
    summaries = summaries or cloudahoy.list_flights(limit=max_flights)
    if max_flights:
        summaries = summaries[:max_flights]
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
                        metadata_path=None,
                        metadata={},
                        has_kml=False,
                    )
                )
                continue

        detail = cloudahoy.fetch_flight(summary.id)
        points_count, has_kml, schema, preview = _describe_detail(
            detail.raw_payload, detail.file_path
        )
        metadata = _extract_metadata(detail.raw_payload)
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
                metadata_path=detail.metadata_path,
                metadata=metadata,
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
    metadata_path: str | None,
    metadata: dict,
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
        metadata_path=metadata_path,
        metadata=metadata,
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
    points_schema_summary = _summarize_points_schema(items)
    return {
        "ready": ready,
        "skipped": skipped,
        "points_schema_summary": points_schema_summary,
    }


def _summarize_points_schema(items: list[ReviewItem]) -> dict:
    by_index: dict[int, dict] = {}
    total_flights = 0
    for item in items:
        if not item.points_schema:
            continue
        total_flights += 1
        for column in item.points_schema:
            index = column.get("index")
            if index is None:
                continue
            name = column.get("name")
            unit = column.get("unit")
            key = int(index)
            entry = by_index.setdefault(
                key,
                {"index": key, "name": name, "unit": unit, "count": 0},
            )
            entry["count"] += 1
            if entry.get("name") == f"col_{key}" and name and name != f"col_{key}":
                entry["name"] = name
                entry["unit"] = unit

    columns = [by_index[idx] for idx in sorted(by_index.keys())]
    unknown = [col for col in columns if col["name"].startswith("col_")]
    return {
        "flights_with_schema": total_flights,
        "column_count": len(columns),
        "columns": columns,
        "unknown_columns": [col["index"] for col in unknown],
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
    keep.update(
        {
            Path(item.metadata_path).resolve()
            for item in items
            if item.metadata_path
        }
    )
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


def _extract_metadata(raw_payload: dict) -> dict:
    flt = raw_payload.get("flt") if isinstance(raw_payload, dict) else {}
    meta = flt.get("Meta") if isinstance(flt, dict) else None
    if not isinstance(meta, dict):
        return {}
    tail_number, aircraft_type, tail_raw = _normalize_tail_number(meta.get("tailNumber"))
    fields = {
        "pilot": meta.get("pilot"),
        "co_pilot": meta.get("coPilot"),
        "pilots": meta.get("pilots"),
        "remarks": meta.get("remarks"),
        "tags": meta.get("tags"),
        "tail_number": tail_number,
        "tail_number_raw": tail_raw,
        "aircraft_type": aircraft_type,
        "aircraft_from": meta.get("from"),
        "aircraft_to": meta.get("to"),
        "event_from": meta.get("e_from"),
        "event_to": meta.get("e_to"),
        "is_sim_flight": meta.get("isSimFlight"),
        "summary": meta.get("summary"),
        "hobbs": meta.get("hobbs"),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


def _normalize_tail_number(value: object) -> tuple[str | None, str | None, list[str] | None]:
    if isinstance(value, str):
        tail = value.strip()
        if _is_placeholder(tail):
            return None, None, [tail]
        return tail, None, None
    if isinstance(value, list):
        tail_candidates = [v for v in value if isinstance(v, str)]
        tail_raw = [v for v in tail_candidates if v]
        tail_number = None
        aircraft_type = None
        for entry in tail_candidates:
            if _is_tail_candidate(entry):
                tail_number = entry
                break
        for entry in tail_candidates:
            if _is_placeholder(entry):
                continue
            if tail_number and entry == tail_number:
                continue
            if not _is_tail_candidate(entry):
                aircraft_type = entry
                break
        return tail_number, aircraft_type, tail_raw or None
    return None, None, None


def _is_tail_candidate(value: str) -> bool:
    stripped = value.strip()
    if _is_placeholder(stripped):
        return False
    if len(stripped) < 2 or len(stripped) > 12:
        return False
    if not all(ch in (string.ascii_letters + string.digits + "-") for ch in stripped):
        return False
    if not any(ch.isdigit() for ch in stripped):
        if not _matches_tail_pattern(stripped):
            return False
    return True


def _is_placeholder(value: str) -> bool:
    return value.strip().upper() in {"", "OTHER", "UNKNOWN"}


def _matches_tail_pattern(value: str) -> bool:
    if "-" not in value:
        return False
    prefix, suffix = value.split("-", 1)
    if not prefix or not suffix:
        return False
    if len(prefix) > 2:
        return False
    if not prefix.isalpha():
        return False
    if not all(ch.isalnum() for ch in suffix):
        return False
    return True


def migrate_flights(
    cloudahoy: CloudAhoyClient,
    flysto: FlyStoClient,
    dry_run: bool = False,
    summaries: list[FlightSummary] | None = None,
    max_flights: int | None = None,
    state: MigrationState | None = None,
    force: bool = False,
) -> tuple[list[MigrationResult], MigrationStats]:
    summaries = summaries or cloudahoy.list_flights(limit=max_flights)
    if max_flights:
        summaries = summaries[:max_flights]
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
