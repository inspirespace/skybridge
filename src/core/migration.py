"""src/core/migration.py module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import time
from pathlib import Path
import string
from typing import Callable

from src.core.cloudahoy.client import CloudAhoyClient
from src.core.cloudahoy.points import build_points_schema, points_preview
from src.core.flysto.client import FlyStoClient
from src.core.models import FlightDetail, FlightSummary, MigrationResult
from src.core.state import MigrationState


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
    file_hash: str | None
    csv_path: str | None
    csv_hash: str | None
    raw_path: str | None
    export_paths: dict[str, str] | None
    points_count: int | None
    points_schema: list[dict]
    points_preview: list[dict]
    metadata_path: str | None
    metadata_hash: str | None
    metadata: dict
    validation_warnings: list[str]
    has_kml: bool

    def to_dict(self) -> dict:
        """Handle to dict."""
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
            "file_hash": self.file_hash,
            "csv_path": self.csv_path,
            "csv_hash": self.csv_hash,
            "raw_path": self.raw_path,
            "export_paths": self.export_paths,
            "points_count": self.points_count,
            "points_schema": self.points_schema,
            "points_preview": self.points_preview,
            "metadata_path": self.metadata_path,
            "metadata_hash": self.metadata_hash,
            "metadata": self.metadata,
            "validation_warnings": self.validation_warnings,
            "has_kml": self.has_kml,
        }


def prepare_review(
    cloudahoy: CloudAhoyClient,
    summaries: list[FlightSummary] | None = None,
    max_flights: int | None = None,
    state: MigrationState | None = None,
    force: bool = False,
    output_path: Path | None = None,
    progress: Callable[[int, int, FlightSummary], None] | None = None,
) -> tuple[list[ReviewItem], str]:
    """Handle prepare review."""
    summaries = summaries or cloudahoy.list_flights(limit=max_flights)
    if max_flights:
        summaries = summaries[:max_flights]
    items: list[ReviewItem] = []

    import_run_at = datetime.now(timezone.utc)
    import_tag = f"cloudahoy:{_format_timestamp_tag(import_run_at)}"

    total_summaries = len(summaries)
    for index, summary in enumerate(summaries, start=1):
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
                        file_hash=None,
                        csv_path=None,
                        csv_hash=None,
                        raw_path=None,
                        export_paths=None,
                        points_count=None,
                        points_schema=[],
                        points_preview=[],
                        metadata_path=None,
                        metadata_hash=None,
                        metadata={},
                        validation_warnings=["skipped: already migrated"],
                        has_kml=False,
                    )
                )
                if progress:
                    progress(index, total_summaries, summary)
                continue

        output_id = summary.fd_id
        detail = cloudahoy.fetch_flight(summary.id, file_id=output_id)
        points_count, has_kml, schema, preview = _describe_detail(
            detail.raw_payload, detail.file_path
        )
        file_hash = _hash_file(detail.file_path)
        csv_hash = _hash_file(detail.csv_path)
        metadata_hash = _hash_file(detail.metadata_path)
        metadata = _extract_metadata(detail.raw_payload)
        validation_warnings = _validate_detail(
            detail=detail,
            points_count=points_count,
            schema=schema,
            metadata=metadata,
        )
        items.append(
            _review_item(
                summary,
                status="ready",
                message=None,
                file_path=detail.file_path,
                file_type=detail.file_type,
                file_hash=file_hash,
                csv_path=detail.csv_path,
                csv_hash=csv_hash,
                raw_path=detail.raw_path,
                export_paths=detail.export_paths,
                points_count=points_count,
                points_schema=schema,
                points_preview=preview,
                metadata_path=detail.metadata_path,
                metadata_hash=metadata_hash,
                metadata=metadata,
                validation_warnings=validation_warnings,
                has_kml=has_kml,
            )
        )
        if progress:
            progress(index, total_summaries, summary)

    review_id = _compute_review_id(items)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "review_id": review_id,
            "count": len(items),
            "summary": _summarize_review(items),
            "items": [item.to_dict() for item in items],
        }
        output_path.write_text(json.dumps(payload, indent=2))

    _cleanup_exports_dir(cloudahoy, items)

    return items, review_id


def _review_item(
    summary: FlightSummary,
    status: str,
    message: str | None,
    file_path: str | None,
    file_type: str | None,
    file_hash: str | None,
    csv_path: str | None,
    csv_hash: str | None,
    raw_path: str | None,
    export_paths: dict[str, str] | None,
    points_count: int | None,
    points_schema: list[dict],
    points_preview: list[dict],
    metadata_path: str | None,
    metadata_hash: str | None,
    metadata: dict,
    validation_warnings: list[str],
    has_kml: bool,
) -> ReviewItem:
    """Internal helper for review item."""
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
        file_hash=file_hash,
        csv_path=csv_path,
        csv_hash=csv_hash,
        raw_path=raw_path,
        export_paths=export_paths,
        points_count=points_count,
        points_schema=points_schema,
        points_preview=points_preview,
        metadata_path=metadata_path,
        metadata_hash=metadata_hash,
        metadata=metadata,
        validation_warnings=validation_warnings,
        has_kml=has_kml,
    )


def _describe_detail(
    raw_payload: dict, file_path: str | None
) -> tuple[int | None, bool, list[dict], list[dict]]:
    """Internal helper for describe detail."""
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
    """Internal helper for summarize review."""
    skipped = sum(1 for item in items if item.status == "skipped")
    ready = sum(1 for item in items if item.status == "ready")
    warnings = sum(1 for item in items if item.validation_warnings)
    points_schema_summary = _summarize_points_schema(items)
    return {
        "ready": ready,
        "skipped": skipped,
        "items_with_warnings": warnings,
        "points_schema_summary": points_schema_summary,
    }


def _summarize_points_schema(items: list[ReviewItem]) -> dict:
    """Internal helper for summarize points schema."""
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
    """Internal helper for cleanup exports dir."""
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
    keep.update(
        {
            Path(item.csv_path).resolve()
            for item in items
            if item.csv_path
        }
    )
    keep.update(
        {
            Path(item.raw_path).resolve()
            for item in items
            if item.raw_path
        }
    )
    keep.update(
        {
            Path(path).resolve()
            for item in items
            for path in (item.export_paths or {}).values()
        }
    )
    for entry in exports_dir.iterdir():
        if not entry.is_file():
            continue
        if entry.resolve() in keep:
            continue
        entry.unlink()


def _payload_has_kml(flt: dict | None) -> bool:
    """Internal helper for payload has kml."""
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
    """Internal helper for extract metadata."""
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


def _extract_crew_assignments(metadata: dict) -> list[dict]:
    """Internal helper for extract crew assignments."""
    crew: list[dict] = []
    by_name: dict[str, dict] = {}

    def add_entry(name: object, role: object, is_pic: bool = False) -> None:
        """Handle add entry."""
        if not isinstance(name, str) or not name.strip():
            return
        role_value = role if isinstance(role, str) and role.strip() else None
        if is_pic:
            role_value = "PIC"
        key = name.strip().lower()
        existing = by_name.get(key)
        entry = {"name": name.strip(), "role": role_value, "is_pic": is_pic}
        if not existing:
            by_name[key] = entry
            return
        # Prefer PIC role if available, otherwise keep first non-empty role.
        if entry.get("is_pic") and not existing.get("is_pic"):
            by_name[key] = entry
            return
        if existing.get("role") is None and entry.get("role") is not None:
            by_name[key] = entry

    pilots = metadata.get("pilots")
    has_pic = False
    if isinstance(pilots, list):
        for entry in pilots:
            if not isinstance(entry, dict):
                continue
            role_name = entry.get("role") if isinstance(entry.get("role"), str) else None
            role_norm = role_name.strip().lower() if role_name else ""
            is_pic = bool(entry.get("PIC") or entry.get("pic"))
            if role_norm in {"pic", "pilot in command"}:
                is_pic = True
            if role_norm in {"safety pilot", "safety"}:
                role_name = "Copilot"
            add_entry(
                entry.get("name"),
                role_name,
                is_pic,
            )
            has_pic = has_pic or is_pic

    # If pilots list exists, it already encodes roles and PIC flags.
    if not isinstance(pilots, list) or not pilots:
        pilot = metadata.get("pilot")
        if isinstance(pilot, list):
            add_entry(pilot[0] if pilot else None, "PIC", True)
        elif isinstance(pilot, str):
            add_entry(pilot, "PIC", True)

        co_pilot = metadata.get("co_pilot")
        if isinstance(co_pilot, list):
            add_entry(co_pilot[0] if co_pilot else None, "Copilot")
        elif isinstance(co_pilot, str):
            add_entry(co_pilot, "Copilot")
    else:
        # CloudAhoy sometimes marks a single "pilot" without PIC; treat as PIC when no PIC exists.
        if not has_pic:
            for entry in by_name.values():
                role_value = entry.get("role") or ""
                if isinstance(role_value, str) and role_value.strip().lower() == "pilot":
                    entry["role"] = "PIC"
                    entry["is_pic"] = True
                    break

    crew = list(by_name.values())
    return crew


def _normalize_remarks(value: object) -> str | None:
    """Internal helper for normalize remarks."""
    if not isinstance(value, str):
        return None
    cleaned = _repair_mojibake(value).strip()
    return cleaned if cleaned else None


def _build_import_tags(import_tag: str) -> list[str]:
    """Internal helper for build import tags."""
    return ["cloudahoy", import_tag]


def _format_timestamp_tag(value: datetime) -> str:
    """Internal helper for format timestamp tag."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _repair_mojibake(value: str) -> str:
    """Internal helper for repair mojibake."""
    if "Ã" not in value and "Â" not in value:
        return value
    for source in ("cp1252", "latin-1"):
        try:
            repaired = value.encode(source).decode("utf-8")
        except UnicodeError:
            continue
        if repaired != value:
            return repaired
    return value


def _compute_review_id(items: list[ReviewItem]) -> str:
    """Internal helper for compute review id."""
    payload = [
        {
            "flight_id": item.flight_id,
            "file_hash": item.file_hash,
            "csv_hash": item.csv_hash,
            "metadata_hash": item.metadata_hash,
        }
        for item in sorted(items, key=lambda i: i.flight_id)
    ]
    blob = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _normalize_tail_number(value: object) -> tuple[str | None, str | None, list[str] | None]:
    """Internal helper for normalize tail number."""
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
    """Internal helper for is tail candidate."""
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
    """Internal helper for is placeholder."""
    return value.strip().upper() in {"", "OTHER", "UNKNOWN"}


def _matches_tail_pattern(value: str) -> bool:
    """Internal helper for matches tail pattern."""
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
    report_path: Path | None = None,
    review_id: str | None = None,
    progress: Callable[[str, dict], None] | None = None,
) -> tuple[list[MigrationResult], MigrationStats]:
    """Handle migrate flights."""
    summaries = summaries or cloudahoy.list_flights(limit=max_flights)
    if max_flights:
        summaries = summaries[:max_flights]
    results: list[MigrationResult] = []
    report_items: list[dict] = []
    succeeded = 0
    failed = 0

    pending: dict[str | None, list[dict]] = {}
    import_run_at = datetime.now(timezone.utc)
    import_tag = f"cloudahoy:{_format_timestamp_tag(import_run_at)}"

    for summary in summaries:
        if progress:
            progress("cloudahoy_fetch_start", {"flight_id": summary.id})
        detail = cloudahoy.fetch_flight(summary.id)
        if progress:
            progress(
                "cloudahoy_fetch_done",
                {"flight_id": summary.id, "file_path": detail.file_path},
            )
        file_hash = _hash_file(detail.file_path)
        csv_hash = _hash_file(detail.csv_path)
        metadata_hash = _hash_file(detail.metadata_path)

        if state and not force:
            record = state.get(summary.id)
            if (
                record
                and record.status == "ok"
                and record.file_hash == file_hash
                and record.csv_hash == csv_hash
                and record.metadata_hash == metadata_hash
            ):
                results.append(
                    MigrationResult(
                        flight_id=summary.id,
                        status="skipped",
                        message="already migrated",
                    )
                )
                continue

            duplicate = state.find_by_hash(file_hash, csv_hash)
            if duplicate and duplicate.status == "ok":
                results.append(
                    MigrationResult(
                        flight_id=summary.id,
                        status="skipped",
                        message=f"duplicate of {duplicate.flight_id}",
                    )
                )
                continue

        metadata = _extract_metadata(detail.raw_payload) if not dry_run else {}
        tail_number = metadata.get("tail_number") if isinstance(metadata, dict) else None
        aircraft_type = metadata.get("aircraft_type") if isinstance(metadata, dict) else None
        crew = _extract_crew_assignments(metadata) if not dry_run else []
        remarks = _normalize_remarks(metadata.get("remarks")) if metadata else None
        tags = _build_import_tags(import_tag)
        pending.setdefault(tail_number, []).append(
            {
                "summary_id": summary.id,
                "detail": detail,
                "file_hash": file_hash,
                "csv_hash": csv_hash,
                "metadata_hash": metadata_hash,
                "tail_number": tail_number,
                "aircraft_type": aircraft_type,
                "crew": crew,
                "remarks": remarks,
                "tags": tags,
                "started_at": summary.started_at,
            }
        )

    # Process uploads grouped by tail number to keep GPX unknown groups isolated.
    for tail_number in sorted(pending.keys(), key=lambda v: v or ""):
        group = pending[tail_number]
        aircraft = None
        if tail_number and not dry_run:
            aircraft_type = next(
                (item.get("aircraft_type") for item in group if item.get("aircraft_type")),
                None,
            )
            aircraft = flysto.ensure_aircraft(tail_number, aircraft_type)

        for item in group:
            detail = item["detail"]
            crew = item.get("crew") or []
            remarks = item.get("remarks")
            tags = item.get("tags") or []
            started_at = item.get("started_at")
            if progress:
                progress("start", {"flight_id": detail.id, "tail_number": tail_number})
            result = _migrate_single(
                detail,
                flysto,
                dry_run,
                aircraft=aircraft,
                crew=crew,
                remarks=remarks,
                tags=tags,
                progress=progress,
            )
            results.append(result)
            if result.status == "ok":
                succeeded += 1
            elif result.status != "skipped":
                failed += 1

            if state:
                state.upsert(
                    item["summary_id"],
                    result.status,
                    result.message,
                    file_hash=item.get("file_hash"),
                    csv_hash=item.get("csv_hash"),
                    metadata_hash=item.get("metadata_hash"),
                )
            report_items.append(
                _build_report_item(
                    detail=detail,
                    status=result.status,
                    message=result.message,
                    tail_number=tail_number,
                    aircraft_type=item.get("aircraft_type"),
                    started_at=started_at,
                    remarks=remarks,
                    tags=tags,
                    crew=crew,
                    flysto=flysto if not dry_run else None,
                )
            )
            if progress:
                progress(
                    "end",
                    {
                        "flight_id": detail.id,
                        "status": result.status,
                        "message": result.message,
                    },
                )

        # Assign the unknown GPX group to this tail after uploading all flights for the tail.
        if not dry_run and aircraft and aircraft.get("id"):
            if progress:
                progress(
                    "flysto_assign_aircraft_group",
                    {"tail_number": tail_number, "aircraft_id": aircraft.get("id")},
                )
            flysto.assign_aircraft(str(aircraft.get("id")), log_format_id="GenericGpx", system_id=None)

    processing_queue = None
    if not dry_run:
        try:
            processing_queue = flysto.log_files_to_process()
        except Exception:
            processing_queue = None

    if progress and processing_queue is not None:
        progress("flysto_processing_queue", {"n_files": processing_queue})

    if report_path:
        _write_import_report(
            report_path=report_path,
            review_id=review_id,
            stats=MigrationStats(
                attempted=len(summaries),
                succeeded=succeeded,
                failed=failed,
            ),
            items=report_items,
            processing_queue=processing_queue,
        )

    return results, MigrationStats(
        attempted=len(summaries),
        succeeded=succeeded,
        failed=failed,
    )


def _migrate_single(
    detail: FlightDetail,
    flysto: FlyStoClient,
    dry_run: bool,
    aircraft: dict | None = None,
    crew: list[dict] | None = None,
    remarks: str | None = None,
    tags: list[str] | None = None,
    progress: Callable[[str, dict], None] | None = None,
) -> MigrationResult:
    """Internal helper for migrate single."""
    try:
        crew = crew or []
        if not dry_run:
            if aircraft is None:
                metadata = _extract_metadata(detail.raw_payload)
                tail_number = metadata.get("tail_number") if isinstance(metadata, dict) else None
                aircraft_type = metadata.get("aircraft_type") if isinstance(metadata, dict) else None
                if tail_number:
                    aircraft = flysto.ensure_aircraft(tail_number, aircraft_type)
            if not crew:
                metadata = _extract_metadata(detail.raw_payload)
                crew = _extract_crew_assignments(metadata)
        if progress:
            progress("flysto_upload_start", {"flight_id": detail.id})
        try:
            upload_result = flysto.upload_flight(detail, dry_run=dry_run)
        except RuntimeError as exc:
            message = str(exc)
            message_lower = message.lower()
            if "already" in message_lower or "duplicate" in message_lower or "exists" in message_lower:
                return MigrationResult(
                    flight_id=detail.id,
                    status="skipped",
                    message=message,
                )
            raise
        if progress:
            progress("flysto_upload_done", {"flight_id": detail.id})
        resolved_log_id = None
        resolved_signature = None
        resolved_format = None
        assign_signature = None
        assign_format = None
        resolved_system_id = None
        resolved_system_format = None
        if upload_result:
            assign_signature = upload_result.signature_hash or upload_result.signature
            assign_format = upload_result.log_format
        if not dry_run and detail.file_path:
            if not resolved_log_id or not resolved_signature or not resolved_format:
                filename = Path(detail.file_path).name
                log_id, signature, log_format = flysto.resolve_log_for_file(filename)
                if not resolved_log_id:
                    resolved_log_id = log_id
                if not resolved_signature:
                    resolved_signature = signature
                if not resolved_format:
                    resolved_format = log_format
            if resolved_log_id and (
                resolved_format == "UnknownGarmin" or assign_format == "UnknownGarmin"
            ):
                resolved_system_format, resolved_system_id = flysto.resolve_log_source_for_log_id(
                    resolved_log_id
                )
            if not assign_signature:
                assign_signature = resolved_signature
            if not assign_format:
                assign_format = resolved_format
            if resolved_system_id:
                assign_signature = resolved_system_id
            if resolved_system_format:
                assign_format = resolved_system_format
            if not assign_format:
                suffix = Path(detail.file_path).name.lower()
                if suffix.endswith(".g3x.csv") or suffix.endswith(".g1000.csv"):
                    assign_format = "UnknownGarmin"
        if not dry_run and aircraft and aircraft.get("id"):
            if progress:
                progress(
                    "flysto_assign_aircraft_file_start",
                    {"flight_id": detail.id, "aircraft_id": aircraft.get("id")},
                )
            flysto.assign_aircraft_for_signature(
                aircraft_id=str(aircraft.get("id")),
                signature=assign_signature,
                log_format_id="GenericGpx",
                resolved_format=assign_format,
            )
            if progress:
                progress(
                    "flysto_assign_aircraft_file_done",
                    {"flight_id": detail.id, "aircraft_id": aircraft.get("id")},
                )
        if not dry_run and crew:
            if progress:
                progress(
                    "flysto_assign_crew_start",
                    {"flight_id": detail.id, "crew_count": len(crew)},
                )
            flysto.assign_crew_for_log_id(resolved_log_id, crew)
            if progress:
                progress(
                    "flysto_assign_crew_done",
                    {"flight_id": detail.id, "crew_count": len(crew)},
                )
        if not dry_run:
            if progress:
                progress(
                    "flysto_assign_metadata_start",
                    {
                        "flight_id": detail.id,
                        "has_remarks": bool(remarks),
                        "tag_count": len(tags or []),
                    },
                )
            flysto.assign_metadata_for_log_id(
                resolved_log_id,
                remarks=remarks,
                tags=tags,
            )
            if progress:
                progress(
                    "flysto_assign_metadata_done",
                    {
                        "flight_id": detail.id,
                        "has_remarks": bool(remarks),
                        "tag_count": len(tags or []),
                    },
                )
        return MigrationResult(flight_id=detail.id, status="ok")
    except Exception as exc:  # noqa: BLE001 - surfacing per-flight failure
        return MigrationResult(
            flight_id=detail.id,
            status="error",
            message=str(exc),
        )


def _hash_file(path: str | None) -> str | None:
    """Internal helper for hash file."""
    if not path:
        return None
    file_path = Path(path)
    if not file_path.exists():
        return None
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _validate_detail(
    detail: FlightDetail,
    points_count: int | None,
    schema: list[dict],
    metadata: dict,
) -> list[str]:
    """Internal helper for validate detail."""
    warnings: list[str] = []
    if not detail.file_path:
        warnings.append("missing export file")
        return warnings
    file_path = Path(detail.file_path)
    if not file_path.exists():
        warnings.append("export file missing on disk")
    if points_count is None or points_count == 0:
        warnings.append("no points found in flt.points")
    if schema:
        names = {col.get("name") for col in schema}
        if "longitude_deg" not in names or "latitude_deg" not in names:
            warnings.append("missing lat/lon columns")
        unknown = [col for col in schema if str(col.get("name", "")).startswith("col_")]
        if unknown:
            warnings.append(f"{len(unknown)} unknown columns remain")
    else:
        warnings.append("points schema unavailable")
    if not metadata.get("tail_number"):
        warnings.append("missing tail number metadata")
    if not metadata.get("pilot") and not metadata.get("pilots"):
        warnings.append("missing pilot metadata")
    return warnings


def _build_report_item(
    detail: FlightDetail,
    status: str,
    message: str | None,
    tail_number: str | None,
    aircraft_type: str | None,
    started_at: datetime | None,
    remarks: str | None,
    tags: list[str] | None,
    crew: list[dict] | None,
    flysto: FlyStoClient | None,
) -> dict:
    """Internal helper for build report item."""
    log_id = None
    signature = None
    log_format = None
    upload_signature = None
    upload_signature_hash = None
    upload_log_id = None
    upload_format = None
    source_format = None
    source_system_id = None
    if flysto and detail.file_path:
        try:
            filename = Path(detail.file_path).name
            upload_result = flysto.upload_cache.get(filename)
            if upload_result:
                upload_signature = upload_result.signature
                upload_signature_hash = upload_result.signature_hash
                upload_log_id = upload_result.log_id
                upload_format = upload_result.log_format
            log_id, signature, log_format = flysto.resolve_log_for_file(
                filename, retries=3, delay_seconds=1.5
            )
            if log_id:
                source_format, source_system_id = flysto.log_source_cache.get(log_id, (None, None))
        except Exception:
            pass
    return {
        "flight_id": detail.id,
        "status": status,
        "message": message,
        "started_at": started_at.isoformat() if isinstance(started_at, datetime) else None,
        "tail_number": tail_number,
        "aircraft_type": aircraft_type,
        "file_path": detail.file_path,
        "remarks": remarks,
        "tags": tags or [],
        "crew": crew or [],
        "flysto_log_id": log_id,
        "flysto_signature": signature,
        "flysto_format": log_format,
        "flysto_upload_signature": upload_signature,
        "flysto_upload_signature_hash": upload_signature_hash,
        "flysto_upload_log_id": upload_log_id,
        "flysto_upload_format": upload_format,
        "flysto_source_format": source_format,
        "flysto_source_system_id": source_system_id,
    }


def _write_import_report(
    report_path: Path,
    review_id: str | None,
    stats: MigrationStats,
    items: list[dict],
    processing_queue: int | None = None,
) -> None:
    """Internal helper for write import report."""
    report_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "review_id": review_id,
        "attempted": stats.attempted,
        "succeeded": stats.succeeded,
        "failed": stats.failed,
        "pending": sum(1 for item in items if not item.get("flysto_log_id")),
        "items": items,
    }
    if processing_queue is not None:
        payload["flysto_processing_queue"] = processing_queue
    report_path.write_text(json.dumps(payload, indent=2))


def verify_import_report(report_path: Path, flysto: FlyStoClient) -> dict[str, int]:
    """Handle verify import report."""
    payload = json.loads(report_path.read_text())
    items = payload.get("items", [])
    resolved = 0
    missing = 0
    total = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        total += 1
        file_path = item.get("file_path")
        if not file_path:
            missing += 1
            continue
        filename = Path(file_path).name
        log_id, signature, log_format = _resolve_log_for_report_item(
            flysto,
            item,
            filename,
            retries=3,
            delay_seconds=1.5,
            logs_limit=250,
        )
        item["flysto_log_id"] = log_id
        item["flysto_signature"] = signature
        item["flysto_format"] = log_format
        if log_id:
            resolved += 1
        else:
            missing += 1
    payload["verified_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["pending"] = sum(1 for item in items if not item.get("flysto_log_id"))
    try:
        processing_queue = flysto.log_files_to_process()
    except Exception:
        processing_queue = None
    if processing_queue is not None:
        payload["flysto_processing_queue"] = processing_queue

    if missing > 0 and (processing_queue == 0 or processing_queue is None):
        resolved = 0
        missing = 0
        total = 0
        for item in items:
            if not isinstance(item, dict):
                continue
            total += 1
            file_path = item.get("file_path")
            if not file_path:
                missing += 1
                continue
            filename = Path(file_path).name
            log_id, signature, log_format = _resolve_log_for_report_item(
                flysto,
                item,
                filename,
                retries=6,
                delay_seconds=2.0,
                logs_limit=500,
            )
            item["flysto_log_id"] = log_id
            item["flysto_signature"] = signature
            item["flysto_format"] = log_format
            if log_id:
                resolved += 1
            else:
                missing += 1
        payload["pending"] = sum(1 for item in items if not item.get("flysto_log_id"))
    payload["verification"] = {
        "attempted": total,
        "resolved": resolved,
        "missing": missing,
    }
    report_path.write_text(json.dumps(payload, indent=2))
    return payload["verification"]


def reconcile_aircraft_from_report(report_path: Path, flysto: FlyStoClient) -> int:
    """Handle reconcile aircraft from report."""
    payload = json.loads(report_path.read_text())
    items = payload.get("items", [])
    updated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        tail_number = item.get("tail_number")
        signature = item.get("flysto_source_system_id") or (
            item.get("flysto_upload_signature_hash")
            or item.get("flysto_upload_signature")
            or item.get("flysto_signature")
        )
        log_format = item.get("flysto_upload_format") or item.get("flysto_format")
        if not tail_number or not signature:
            file_path = item.get("file_path")
            if file_path:
                filename = Path(file_path).name
                try:
                    _log_id, signature, log_format = _resolve_log_for_report_item(
                        flysto,
                        item,
                        filename,
                        retries=3,
                        delay_seconds=1.5,
                        logs_limit=250,
                    )
                except Exception:
                    signature = signature or None
                    log_format = log_format or None
        if item.get("flysto_log_id"):
            try:
                source_format, source_system_id = flysto.resolve_log_source_for_log_id(
                    item["flysto_log_id"]
                )
                if source_system_id:
                    signature = source_system_id
                if source_format:
                    log_format = source_format
            except Exception:
                pass
        if not tail_number or not signature:
            continue
        if not log_format:
            if Path(item.get("file_path", "")).name.lower().endswith(".g3x.csv"):
                log_format = "UnknownGarmin"
            else:
                log_format = "GenericGpx"
        aircraft = flysto.ensure_aircraft(tail_number, item.get("aircraft_type"))
        if not aircraft or not aircraft.get("id"):
            continue
        flysto.assign_aircraft_for_signature(
            aircraft_id=str(aircraft.get("id")),
            signature=signature,
            log_format_id="GenericGpx",
            resolved_format=log_format,
        )
        updated += 1
    payload["aircraft_reconciled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["aircraft_reconciled"] = updated
    report_path.write_text(json.dumps(payload, indent=2))
    return updated


def reconcile_crew_from_report(
    report_path: Path,
    flysto: FlyStoClient,
    review_path: Path | None = None,
    cloudahoy: CloudAhoyClient | None = None,
) -> int:
    """Handle reconcile crew from report."""
    payload = json.loads(report_path.read_text())
    items = payload.get("items", [])
    review_metadata: dict[str, dict] = {}
    if review_path and review_path.exists():
        review = json.loads(review_path.read_text())
        for entry in review.get("items", []):
            if not isinstance(entry, dict):
                continue
            flight_id = entry.get("flight_id")
            metadata = entry.get("metadata")
            if isinstance(flight_id, str) and isinstance(metadata, dict):
                review_metadata[flight_id] = metadata
    updated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        log_id = item.get("flysto_log_id") or item.get("flysto_upload_log_id")
        file_path = item.get("file_path")
        if file_path:
            try:
                resolved_log_id, _signature, _format = _resolve_log_for_report_item(
                    flysto,
                    item,
                    Path(file_path).name,
                    retries=3,
                    delay_seconds=1.5,
                    logs_limit=250,
                    prefer_persisted_log_id=False,
                )
            except Exception:
                resolved_log_id = None
            if resolved_log_id:
                log_id = resolved_log_id
                item["flysto_log_id"] = resolved_log_id
        if not log_id:
            continue
        crew = item.get("crew")
        if not isinstance(crew, list) or not crew:
            metadata = review_metadata.get(item.get("flight_id"))
            if isinstance(metadata, dict):
                crew = _extract_crew_assignments(metadata)
        if not crew and cloudahoy:
            try:
                metadata = cloudahoy.fetch_metadata(str(item.get("flight_id")))
                if isinstance(metadata, dict):
                    crew = _extract_crew_assignments(metadata)
            except Exception:
                crew = None
        if not crew:
            continue
        item["crew"] = crew
        flysto.assign_crew_for_log_id(log_id, crew)
        if not _log_metadata_has_crew(flysto.fetch_log_metadata(log_id), log_id):
            time.sleep(2)
            if file_path:
                try:
                    refreshed_log_id, _signature, _format = _resolve_log_for_report_item(
                        flysto,
                        item,
                        Path(file_path).name,
                        retries=3,
                        delay_seconds=1.5,
                        logs_limit=250,
                        prefer_persisted_log_id=False,
                    )
                except Exception:
                    refreshed_log_id = None
                if refreshed_log_id:
                    log_id = refreshed_log_id
                    item["flysto_log_id"] = refreshed_log_id
            flysto.assign_crew_for_log_id(log_id, crew)
        updated += 1
    payload["crew_reconciled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["crew_reconciled"] = updated
    report_path.write_text(json.dumps(payload, indent=2))
    return updated


def _log_metadata_has_crew(metadata: dict[str, Any] | None, log_id: str | None) -> bool:
    """Internal helper for log metadata has crew."""
    if not metadata or not log_id:
        return False
    items = metadata.get("items")
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict) or item.get("id") != log_id:
            continue
        annotations = item.get("annotations")
        if isinstance(annotations, dict) and annotations.get("crew"):
            return True
    return False


def _is_missing_flysto_log_error(error: Exception, *, operation: str) -> bool:
    """Return True when FlySto rejected an operation because the log no longer exists."""
    message = str(error).lower()
    return f"flysto {operation} failed: 404" in message and "log not found" in message


def _resolve_log_for_report_item(
    flysto: FlyStoClient,
    item: dict[str, Any],
    filename: str,
    *,
    retries: int,
    delay_seconds: float,
    logs_limit: int,
    prefer_persisted_log_id: bool = True,
) -> tuple[str | None, str | None, str | None]:
    """Prefer persisted/upload-time identifiers before querying FlySto summaries again."""
    persisted_log_id = (
        item.get("flysto_log_id") or item.get("flysto_upload_log_id")
        if prefer_persisted_log_id
        else item.get("flysto_upload_log_id")
    )
    persisted_signature = (
        item.get("flysto_source_system_id")
        or item.get("flysto_upload_signature_hash")
        or item.get("flysto_upload_signature")
        or item.get("flysto_signature")
    )
    persisted_format = item.get("flysto_upload_format") or item.get("flysto_format")
    if persisted_log_id or persisted_signature or persisted_format:
        return (
            str(persisted_log_id) if persisted_log_id else None,
            str(persisted_signature) if persisted_signature else None,
            str(persisted_format) if persisted_format else None,
        )
    upload_cache = getattr(flysto, "upload_cache", None)
    if isinstance(upload_cache, dict):
        upload_result = upload_cache.get(filename)
        if upload_result:
            log_id = getattr(upload_result, "log_id", None)
            signature = (
                getattr(upload_result, "signature_hash", None)
                or getattr(upload_result, "signature", None)
            )
            log_format = getattr(upload_result, "log_format", None)
            if log_id or signature or log_format:
                return log_id, signature, log_format
    return flysto.resolve_log_for_file(
        filename,
        retries=retries,
        delay_seconds=delay_seconds,
        logs_limit=logs_limit,
    )


def reconcile_metadata_from_report(
    report_path: Path,
    flysto: FlyStoClient,
) -> int:
    """Handle reconcile metadata from report."""
    payload = json.loads(report_path.read_text())
    items = payload.get("items", [])
    updated = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        remarks = item.get("remarks")
        tags = item.get("tags")
        if not remarks and not tags:
            continue
        log_id = item.get("flysto_log_id") or item.get("flysto_upload_log_id")
        file_path = item.get("file_path")
        if file_path:
            try:
                resolved_log_id, _signature, _format = _resolve_log_for_report_item(
                    flysto,
                    item,
                    Path(file_path).name,
                    retries=3,
                    delay_seconds=1.5,
                    logs_limit=250,
                    prefer_persisted_log_id=False,
                )
            except Exception:
                resolved_log_id = None
            if resolved_log_id:
                log_id = resolved_log_id
                item["flysto_log_id"] = resolved_log_id
        if not log_id:
            continue
        try:
            flysto.assign_metadata_for_log_id(log_id, remarks=remarks, tags=tags)
        except Exception as error:
            if (
                not file_path
                or not _is_missing_flysto_log_error(error, operation="log-annotations")
            ):
                raise
            try:
                refreshed_log_id, _signature, _format = _resolve_log_for_report_item(
                    flysto,
                    item,
                    Path(file_path).name,
                    retries=3,
                    delay_seconds=1.5,
                    logs_limit=250,
                    prefer_persisted_log_id=False,
                )
            except Exception:
                refreshed_log_id = None
            if not refreshed_log_id or refreshed_log_id == log_id:
                raise
            log_id = refreshed_log_id
            item["flysto_log_id"] = refreshed_log_id
            flysto.assign_metadata_for_log_id(log_id, remarks=remarks, tags=tags)
        updated += 1
    payload["metadata_reconciled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload["metadata_reconciled"] = updated
    report_path.write_text(json.dumps(payload, indent=2))
    return updated
