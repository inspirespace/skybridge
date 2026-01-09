"""Additional migration coverage tests."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json

import pytest

from src.core.migration import (
    _log_metadata_has_crew,
    _migrate_single,
    _summarize_points_schema,
    _validate_detail,
    prepare_review,
)
from src.core.models import FlightDetail, FlightSummary, MigrationResult


@dataclass
class FakeStateRecord:
    flight_id: str
    status: str


class FakeState:
    def __init__(self, skip_id: str | None = None) -> None:
        self._skip_id = skip_id

    def get(self, flight_id: str):
        if flight_id == self._skip_id:
            return FakeStateRecord(flight_id=flight_id, status="ok")
        return None


class FakeCloudAhoy:
    def __init__(self, summaries, details, exports_dir: Path):
        self._summaries = summaries
        self._details = details
        self.exports_dir = exports_dir

    def list_flights(self, limit=None):
        return self._summaries if limit is None else self._summaries[:limit]

    def fetch_flight(self, flight_id: str, file_id: str | None = None):
        return self._details[flight_id]


class DummyFlySto:
    def __init__(self):
        self.upload_calls = 0

    def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
        self.upload_calls += 1
        raise RuntimeError("Already exists")

    def ensure_aircraft(self, *args, **kwargs):
        return {"id": "air-1"}

    def assign_aircraft_for_signature(self, *args, **kwargs):
        return None

    def assign_crew_for_log_id(self, *args, **kwargs):
        return None

    def assign_metadata_for_log_id(self, *args, **kwargs):
        return None

    def resolve_log_for_file(self, *args, **kwargs):
        return "log-1", "sig-1", "GenericGpx"

    def resolve_log_source_for_log_id(self, *args, **kwargs):
        return "UnknownGarmin", "sys-1"


class DummyFlyStoError(DummyFlySto):
    def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
        raise RuntimeError("boom")


def test_prepare_review_skips_state_and_cleans_exports(tmp_path: Path):
    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True)
    keep_file = exports_dir / "keep.gpx"
    keep_file.write_text("keep")
    extra_file = exports_dir / "extra.gpx"
    extra_file.write_text("remove")

    summaries = [
        FlightSummary("A1", datetime.now(timezone.utc), None, None, None),
        FlightSummary("A2", datetime.now(timezone.utc), None, None, None),
    ]
    detail = FlightDetail(
        id="A2",
        raw_payload={"flt": {"points": [[1, 2], [3, 4]], "Meta": {"pilot": "Alex", "tailNumber": "N123"}}},
        file_path=str(keep_file),
        metadata_path=str(exports_dir / "meta.json"),
        csv_path=str(exports_dir / "data.csv"),
        raw_path=str(exports_dir / "raw.json"),
        export_paths={"alt": str(exports_dir / "alt.gpx")},
    )
    for path in [detail.metadata_path, detail.csv_path, detail.raw_path, detail.export_paths["alt"]]:
        Path(path).write_text("data")

    cloudahoy = FakeCloudAhoy(summaries, {"A2": detail}, exports_dir)
    output_path = tmp_path / "review.json"

    items, review_id = prepare_review(
        cloudahoy=cloudahoy,
        summaries=summaries,
        state=FakeState(skip_id="A1"),
        output_path=output_path,
    )
    assert review_id
    assert any(item.status == "skipped" for item in items)
    assert output_path.exists()
    assert not extra_file.exists()


def test_validate_detail_warns_missing_file():
    detail = FlightDetail(id="F1", raw_payload={})
    warnings = _validate_detail(detail, points_count=None, schema=[], metadata={})
    assert "missing export file" in warnings


def test_migrate_single_duplicate_marks_skipped():
    detail = FlightDetail(id="F1", raw_payload={}, file_path="/tmp/f1.gpx")
    result = _migrate_single(detail, DummyFlySto(), dry_run=False)
    assert result.status == "skipped"


def test_migrate_single_error_marks_failure():
    detail = FlightDetail(id="F2", raw_payload={}, file_path="/tmp/f2.gpx")
    result = _migrate_single(detail, DummyFlyStoError(), dry_run=False)
    assert result.status == "error"


def test_log_metadata_has_crew():
    assert _log_metadata_has_crew(None, None) is False
    assert _log_metadata_has_crew({"items": [{"id": "log-1", "annotations": {"crew": [1]}}]}, "log-1")


def test_summarize_points_schema_flags_unknown():
    items = [
        type(
            "Item",
            (),
            {
                "points_schema": [
                    {"index": 0, "name": "col_0", "unit": None},
                    {"index": 1, "name": "latitude_deg", "unit": None},
                ]
            },
        )()
    ]
    summary = _summarize_points_schema(items)
    assert summary["unknown_columns"] == [0]
