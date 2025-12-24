from __future__ import annotations

from datetime import datetime

from src.migration import migrate_flights
from src.models import FlightDetail, FlightSummary


class FakeCloudAhoy:
    def __init__(self, summaries: list[FlightSummary], details: dict[str, FlightDetail]):
        self._summaries = summaries
        self._details = details

    def list_flights(self, limit: int | None = None):
        return self._summaries if limit is None else self._summaries[:limit]

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        return self._details[flight_id]


class FakeFlySto:
    def __init__(self):
        self.uploaded: list[str] = []
        self.assigned_files: list[tuple[str, str]] = []
        self.assigned_unknown: list[str] = []
        self.ensured: list[str] = []
        self.metadata_calls: list[tuple[str, str | None, list[str]]] = []

    def ensure_aircraft(self, tail_number: str, aircraft_type: str | None = None):
        self.ensured.append(tail_number)
        return {"id": f"id-{tail_number}", "tail-number": tail_number}

    def upload_flight(self, detail: FlightDetail, dry_run: bool = False):
        self.uploaded.append(detail.id)

    def assign_aircraft_for_file(self, filename: str, aircraft_id: str):
        self.assigned_files.append((filename, aircraft_id))

    def assign_crew_for_file(self, filename: str, crew: list[dict]):
        # Not relevant for grouping test
        return None

    def assign_aircraft(self, aircraft_id: str, log_format_id: str = "GenericGpx", system_id=None):
        # Track group assignment calls
        self.assigned_unknown.append(aircraft_id)

    def assign_metadata_for_file(self, filename: str, remarks: str | None = None, tags: list[str] | None = None):
        self.metadata_calls.append((filename, remarks, tags or []))


def _detail(flight_id: str, tail: str) -> FlightDetail:
    return FlightDetail(
        id=flight_id,
        raw_payload={"flt": {"Meta": {"tailNumber": tail}}},
        file_path=f"/tmp/{flight_id}.gpx",
        metadata_path=f"/tmp/{flight_id}.meta.json",
        csv_path=f"/tmp/{flight_id}.csv",
    )


def test_grouped_uploads_assign_unknown_per_tail():
    summaries = [
        FlightSummary("A1", datetime.utcnow(), None, None, None),
        FlightSummary("A2", datetime.utcnow(), None, None, None),
        FlightSummary("B1", datetime.utcnow(), None, None, None),
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
    assert len(flysto.assigned_files) == 3

    # Unknown group assignment should run once per tail
    assert set(flysto.assigned_unknown) == {"id-D-KLVW", "id-OE-9487"}


def test_migration_adds_cloudahoy_tag_and_remarks():
    started_at = datetime(2025, 3, 20, 15, 37)
    summaries = [
        FlightSummary("A1", started_at, None, None, None),
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
    filename, remarks, tags = flysto.metadata_calls[0]
    assert filename == "A1.gpx"
    assert remarks == "Night flight"
    assert "cloudahoy" in tags
    assert "cloudahoy:2025-03-20T15:37Z" in tags


def test_migration_repairs_mojibake_remarks():
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

    _filename, remarks, _tags = flysto.metadata_calls[0]
    assert remarks == "Solo Überland"
