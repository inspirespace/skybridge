"""tests/test_migration_flow.py module."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.core.migration import migrate_flights
from src.core.models import FlightDetail, FlightSummary
from src.core.flysto.client import UploadResult


class DummyCloudAhoy:
    def __init__(self, detail: FlightDetail) -> None:
        """Internal helper for init  ."""
        self._detail = detail

    def list_flights(self, limit=None):
        """Handle list flights."""
        return [
            FlightSummary(
                id=self._detail.id,
                started_at=datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc),
                duration_seconds=1200,
                aircraft_type="WT9",
                tail_number="D-KBUH",
            )
        ]

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        """Handle fetch flight."""
        return self._detail


class DummyFlySto:
    def __init__(self) -> None:
        """Internal helper for init  ."""
        self.assigned: list[tuple[str | None, str | None]] = []
        self.assigned_crews: list[str] = []
        self.assigned_metadata: list[str] = []

    def ensure_aircraft(self, tail_number, aircraft_type=None):
        """Handle ensure aircraft."""
        return {"id": "aircraft-1"}

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False):
        """Handle upload flight."""
        return UploadResult(
            signature="flight.g3x.csv/hash123/log789",
            log_id="log789",
            log_format="UnknownGarmin",
            signature_hash="hash123",
        )

    def resolve_log_for_file(self, filename: str, **_kwargs):
        """Handle resolve log for file."""
        return "log-1", "sig-log", "UnknownGarmin"

    def resolve_log_source_for_log_id(self, log_id: str, include_annotations: bool = True):
        """Handle resolve log source for log id."""
        return "UnknownGarmin", "system id: D-KBUH"

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ) -> None:
        """Handle assign aircraft for signature."""
        self.assigned.append((signature, resolved_format))

    def assign_aircraft(
        self,
        aircraft_id: str,
        log_format_id: str = "GenericGpx",
        system_id: str | None = None,
    ) -> None:
        """Handle assign aircraft."""
        return None

    def assign_crew_for_log_id(self, log_id: str | None, crew):
        """Handle assign crew for log id."""
        if log_id:
            self.assigned_crews.append(log_id)

    def assign_metadata_for_log_id(self, log_id: str | None, remarks=None, tags=None):
        """Handle assign metadata for log id."""
        if log_id:
            self.assigned_metadata.append(log_id)
        return None

    def log_files_to_process(self):
        """Handle log files to process."""
        return 0


def test_migrate_flights_uses_system_id_for_unknown_garmin(tmp_path: Path):
    """Test migrate flights uses system id for unknown garmin."""
    file_path = tmp_path / "flight.g3x.csv"
    file_path.write_text("data")
    raw_payload = {
        "flt": {
            "Meta": {
                "tailNumber": "D-KBUH",
                "aircraftType": "WT9",
                "pilots": [{"name": "Alex", "role": "Student"}],
            }
        }
    }
    detail = FlightDetail(
        id="flight-1",
        raw_payload=raw_payload,
        file_path=str(file_path),
    )
    cloudahoy = DummyCloudAhoy(detail)
    flysto = DummyFlySto()

    results, stats = migrate_flights(
        cloudahoy=cloudahoy,
        flysto=flysto,
        dry_run=False,
        summaries=None,
        max_flights=None,
        state=None,
        force=True,
        report_path=None,
        review_id=None,
        progress=None,
    )

    assert stats.succeeded == 1
    assert flysto.assigned == [("system id: D-KBUH", "UnknownGarmin")]
    assert flysto.assigned_crews == ["log789"]
    assert flysto.assigned_metadata == ["log789"]


class DummyFlyStoSignature(DummyFlySto):
    def resolve_log_source_for_log_id(self, log_id: str, include_annotations: bool = True):
        """Handle resolve log source for log id."""
        return None, None

    def resolve_log_for_file(self, filename: str, **_kwargs):
        """Handle resolve log for file."""
        return "log-1", "sig-log", "GenericGpx"

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False):
        """Handle upload flight."""
        return UploadResult(
            signature="flight.gpx/hash999/log555",
            log_id="log555",
            log_format="GenericGpx",
            signature_hash="hash999",
        )


def test_migrate_flights_uses_upload_signature_hash(tmp_path: Path):
    """Test migrate flights uses upload signature hash."""
    file_path = tmp_path / "flight.gpx"
    file_path.write_text("data")
    raw_payload = {"flt": {"Meta": {"tailNumber": "D-KBUH", "aircraftType": "WT9"}}}
    detail = FlightDetail(
        id="flight-1",
        raw_payload=raw_payload,
        file_path=str(file_path),
    )
    cloudahoy = DummyCloudAhoy(detail)
    flysto = DummyFlyStoSignature()

    results, stats = migrate_flights(
        cloudahoy=cloudahoy,
        flysto=flysto,
        dry_run=False,
        summaries=None,
        max_flights=None,
        state=None,
        force=True,
        report_path=None,
        review_id=None,
        progress=None,
    )

    assert stats.succeeded == 1
    assert flysto.assigned == [("hash999", "GenericGpx")]


class DummyFlyStoMetadata404(DummyFlyStoSignature):
    def assign_metadata_for_log_id(self, log_id: str | None, remarks=None, tags=None):
        if log_id == "log-1":
            raise RuntimeError("FlySto log-annotations failed: 404 Log not found")
        super().assign_metadata_for_log_id(log_id, remarks=remarks, tags=tags)


def test_migrate_flights_prefers_upload_log_id_for_metadata(tmp_path: Path):
    """Test migrate flights uses upload log id instead of stale filename lookup for metadata."""
    file_path = tmp_path / "flight.gpx"
    file_path.write_text("data")
    raw_payload = {"flt": {"Meta": {"tailNumber": "D-KBUH", "aircraftType": "WT9"}}}
    detail = FlightDetail(
        id="flight-1",
        raw_payload=raw_payload,
        file_path=str(file_path),
    )
    cloudahoy = DummyCloudAhoy(detail)
    flysto = DummyFlyStoMetadata404()

    _results, stats = migrate_flights(
        cloudahoy=cloudahoy,
        flysto=flysto,
        dry_run=False,
        summaries=None,
        max_flights=None,
        state=None,
        force=True,
        report_path=None,
        review_id=None,
        progress=None,
    )

    assert stats.succeeded == 1
    assert flysto.assigned_metadata == ["log555"]
