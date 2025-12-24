from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import string

from src.cloudahoy.client import CloudAhoyClient
from src.cloudahoy.points import build_points_schema, points_preview
from src.flysto.client import FlyStoClient
from src.models import FlightDetail, FlightSummary, MigrationResult
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
    file_hash: str | None
    csv_path: str | None
    csv_hash: str | None
    points_count: int | None
    points_schema: list[dict]
    points_preview: list[dict]
    metadata_path: str | None
    metadata_hash: str | None
    metadata: dict
    validation_warnings: list[str]
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
            "file_hash": self.file_hash,
            "csv_path": self.csv_path,
            "csv_hash": self.csv_hash,
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
) -> tuple[list[ReviewItem], str]:
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
                        file_hash=None,
                        csv_path=None,
                        csv_hash=None,
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
                continue

        detail = cloudahoy.fetch_flight(summary.id)
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

    review_id = _compute_review_id(items)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
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
    points_count: int | None,
    points_schema: list[dict],
    points_preview: list[dict],
    metadata_path: str | None,
    metadata_hash: str | None,
    metadata: dict,
    validation_warnings: list[str],
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
        file_hash=file_hash,
        csv_path=csv_path,
        csv_hash=csv_hash,
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
    warnings = sum(1 for item in items if item.validation_warnings)
    points_schema_summary = _summarize_points_schema(items)
    return {
        "ready": ready,
        "skipped": skipped,
        "items_with_warnings": warnings,
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
    keep.update(
        {
            Path(item.csv_path).resolve()
            for item in items
            if item.csv_path
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


def _extract_crew_assignments(metadata: dict) -> list[dict]:
    crew: list[dict] = []
    by_name: dict[str, dict] = {}

    def add_entry(name: object, role: object, is_pic: bool = False) -> None:
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
    if not isinstance(value, str):
        return None
    cleaned = _repair_mojibake(value).strip()
    return cleaned if cleaned else None


def _build_import_tags(started_at: datetime) -> list[str]:
    when = _format_timestamp_tag(started_at)
    return ["cloudahoy", f"cloudahoy:{when}"]


def _format_timestamp_tag(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _repair_mojibake(value: str) -> str:
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

    pending: dict[str | None, list[dict]] = {}

    for summary in summaries:
        detail = cloudahoy.fetch_flight(summary.id)
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
        tags = _build_import_tags(summary.started_at)
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
            result = _migrate_single(
                detail,
                flysto,
                dry_run,
                aircraft=aircraft,
                crew=crew,
                remarks=remarks,
                tags=tags,
            )
            results.append(result)
            if result.status == "ok":
                succeeded += 1
            else:
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

        # Assign the unknown GPX group to this tail after uploading all flights for the tail.
        if not dry_run and aircraft and aircraft.get("id"):
            flysto.assign_aircraft(str(aircraft.get("id")), log_format_id="GenericGpx", system_id=None)

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
) -> MigrationResult:
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
        flysto.upload_flight(detail, dry_run=dry_run)
        if not dry_run and aircraft and aircraft.get("id") and detail.file_path:
            filename = Path(detail.file_path).name
            flysto.assign_aircraft_for_file(filename, str(aircraft.get("id")))
        if not dry_run and crew and detail.file_path:
            filename = Path(detail.file_path).name
            flysto.assign_crew_for_file(filename, crew)
        if not dry_run and detail.file_path:
            filename = Path(detail.file_path).name
            flysto.assign_metadata_for_file(filename, remarks=remarks, tags=tags)
        return MigrationResult(flight_id=detail.id, status="ok")
    except Exception as exc:  # noqa: BLE001 - surfacing per-flight failure
        return MigrationResult(
            flight_id=detail.id,
            status="error",
            message=str(exc),
        )


def _hash_file(path: str | None) -> str | None:
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
