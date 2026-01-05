from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile

from src.core.migration import migrate_flights, verify_import_report
from src.core.models import FlightDetail, FlightSummary


class FakeCloudAhoy:
    def __init__(self, summaries: list[FlightSummary], details: dict[str, FlightDetail]):
    """Internal helper for init  ."""
        self._summaries = summaries
        self._details = details

    def list_flights(self, limit: int | None = None):
    """Handle list flights."""
        return self._summaries if limit is None else self._summaries[:limit]

    def fetch_flight(self, flight_id: str) -> FlightDetail:
    """Handle fetch flight."""
        return self._details[flight_id]


class FakeFlySto:
    def __init__(self):
    """Internal helper for init  ."""
        self.uploaded: list[str] = []
        self.assigned_signatures: list[tuple[str, str | None, str | None]] = []
        self.assigned_unknown: list[str] = []
        self.ensured: list[str] = []
        self.metadata_calls: list[tuple[str | None, str | None, list[str]]] = []

    def ensure_aircraft(self, tail_number: str, aircraft_type: str | None = None):
    """Handle ensure aircraft."""
        self.ensured.append(tail_number)
        return {"id": f"id-{tail_number}", "tail-number": tail_number}

    def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
    """Handle upload flight."""
        self.uploaded.append(detail.id)

    def assign_aircraft_for_signature(
    """Handle assign aircraft for signature."""
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ):
        self.assigned_signatures.append((aircraft_id, signature, resolved_format or log_format_id))

    def assign_crew_for_log_id(self, log_id: str | None, crew: list[dict]):
    """Handle assign crew for log id."""
        # Not relevant for grouping test
        return None

    def assign_aircraft(self, aircraft_id: str, log_format_id: str = "GenericGpx", system_id=None):
    """Handle assign aircraft."""
        # Track group assignment calls
        self.assigned_unknown.append(aircraft_id)

    def assign_metadata_for_log_id(
    """Handle assign metadata for log id."""
        self,
        log_id: str | None,
        remarks: str | None = None,
        tags: list[str] | None = None,
    ):
        self.metadata_calls.append((log_id, remarks, tags or []))

    def resolve_log_for_file(
    """Handle resolve log for file."""
        self,
        filename: str,
        retries: int = 8,
        delay_seconds: float = 3.0,
        logs_limit: int = 250,
    ):
        return f"log-{filename}", f"sig-{filename}", "GenericGpx"


def _detail(flight_id: str, tail: str) -> FlightDetail:
"""Internal helper for detail."""
    return FlightDetail(
        id=flight_id,
        raw_payload={"flt": {"Meta": {"tailNumber": tail}}},
        file_path=f"/tmp/{flight_id}.gpx",
        metadata_path=f"/tmp/{flight_id}.meta.json",
        csv_path=f"/tmp/{flight_id}.csv",
    )


def test_grouped_uploads_assign_unknown_per_tail():
"""Test grouped uploads assign unknown per tail."""
    summaries = [
    FlightSummary("A1", datetime.now(timezone.utc), None, None, None),
    FlightSummary("A2", datetime.now(timezone.utc), None, None, None),
    FlightSummary("B1", datetime.now(timezone.utc), None, None, None),
    ]
    details = {
        "A1": _detail("A1", "D-KLVW"),
        "A2": _detail("A2", "D-KLVW"),
        "B1": _detail("B1", "OE-9487"),
    }
    cloudahoy = FakeCloudAhoy(summaries, details)
    flysto = FakeFlySto()

    results, stats = migrate_flights(cloudahoy, flysto, dry_run=False)

    assert stats.attempted == 3
    assert stats.succeeded == 3
    assert [r.status for r in results] == ["ok", "ok", "ok"]

    # All flights uploaded
    assert set(flysto.uploaded) == {"A1", "A2", "B1"}

    # Per-file aircraft assignment should happen for each file
    assert len(flysto.assigned_signatures) == 3

    # Unknown group assignment should run once per tail
    assert set(flysto.assigned_unknown) == {"id-D-KLVW", "id-OE-9487"}


def test_migration_adds_cloudahoy_tag_and_remarks():
"""Test migration adds cloudahoy tag and remarks."""
    summaries = [
        FlightSummary("A1", datetime(2025, 3, 20, 15, 37), None, None, None),
    ]
    detail = FlightDetail(
        id="A1",
        raw_payload={
            "flt": {
                "Meta": {
                    "remarks": "Night flight",
                    "tailNumber": "D-KLVW",
                }
            }
        },
        file_path="/tmp/A1.gpx",
        metadata_path="/tmp/A1.meta.json",
        csv_path="/tmp/A1.csv",
    )
    details = {"A1": detail}
    cloudahoy = FakeCloudAhoy(summaries, details)
    flysto = FakeFlySto()

    migrate_flights(cloudahoy, flysto, dry_run=False)

    assert flysto.metadata_calls
    log_id, remarks, tags = flysto.metadata_calls[0]
    assert log_id == "log-A1.gpx"
    assert remarks == "Night flight"
    assert "cloudahoy" in tags
    assert any(tag.startswith("cloudahoy:") for tag in tags)


def test_migration_repairs_mojibake_remarks():
"""Test migration repairs mojibake remarks."""
    summaries = [
        FlightSummary("A2", datetime(2025, 9, 4, 15, 26), None, None, None),
    ]
    detail = FlightDetail(
        id="A2",
        raw_payload={
            "flt": {
                "Meta": {
                    "remarks": "Solo Ãœberland",
                    "tailNumber": "D-KLVW",
                }
            }
        },
        file_path="/tmp/A2.gpx",
        metadata_path="/tmp/A2.meta.json",
        csv_path="/tmp/A2.csv",
    )
    cloudahoy = FakeCloudAhoy(summaries, {"A2": detail})
    flysto = FakeFlySto()

    migrate_flights(cloudahoy, flysto, dry_run=False)

    _log_id, remarks, _tags = flysto.metadata_calls[0]
    assert remarks == "Solo Überland"


def test_import_report_written():
"""Test import report written."""
    summaries = [
        FlightSummary("A3", datetime(2025, 7, 23, 16, 29), None, None, None),
    ]
    detail = FlightDetail(
        id="A3",
        raw_payload={"flt": {"Meta": {"tailNumber": "D-KLVW"}}},
        file_path="/tmp/A3.gpx",
        metadata_path="/tmp/A3.meta.json",
        csv_path="/tmp/A3.csv",
    )
    cloudahoy = FakeCloudAhoy(summaries, {"A3": detail})
    flysto = FakeFlySto()

    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = Path(temp_dir) / "report.json"
        migrate_flights(
            cloudahoy,
            flysto,
            dry_run=False,
            report_path=report_path,
            review_id="review-123",
        )
        payload = json.loads(report_path.read_text())
        assert payload["review_id"] == "review-123"
        assert payload["attempted"] == 1
        assert payload["succeeded"] == 1
        assert payload["failed"] == 0
        assert payload["items"][0]["flight_id"] == "A3"


def test_verify_import_report_updates_log_ids():
"""Test verify import report updates log ids."""
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = Path(temp_dir) / "report.json"
        report_path.write_text(
            json.dumps(
                {
                    "items": [
                        {"flight_id": "A4", "file_path": "/tmp/A4.gpx"},
                        {"flight_id": "A5", "file_path": None},
                    ]
                }
            )
        )
        flysto = FakeFlySto()
        summary = verify_import_report(report_path, flysto)
        payload = json.loads(report_path.read_text())
        assert summary["attempted"] == 2
        assert summary["resolved"] == 1
        assert summary["missing"] == 1
        assert payload["items"][0]["flysto_log_id"] == "log-A4.gpx"
