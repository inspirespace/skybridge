"""Extra migration helper coverage tests."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json


from src.core.migration import (
    _build_report_item,
    _describe_detail,
    _extract_crew_assignments,
    _is_tail_candidate,
    _matches_tail_pattern,
    _normalize_tail_number,
    _payload_has_kml,
    reconcile_aircraft_from_report,
    reconcile_metadata_from_report,
    verify_import_report,
)
from src.core.models import FlightDetail
from src.core.flysto.client import UploadResult


class DummyFlySto:
    def __init__(self) -> None:
        self.upload_cache: dict[str, UploadResult] = {}
        self.log_source_cache: dict[str, tuple[str | None, str | None]] = {}
        self.resolve_calls: list[dict] = []
        self.assigned: list[tuple[str, str | None, str | None]] = []
        self.metadata_calls: list[tuple[str, str | None, list[str] | None]] = []
        self.ensure_calls: list[tuple[str, str | None]] = []
        self.next_processing: int | None = None
        self.resolve_sequence: list[tuple[str | None, str | None, str | None]] = []

    def resolve_log_for_file(self, filename: str, **kwargs):
        self.resolve_calls.append({"filename": filename, **kwargs})
        if self.resolve_sequence:
            return self.resolve_sequence.pop(0)
        return f"log-{filename}", f"sig-{filename}", "GenericGpx"

    def log_files_to_process(self) -> int | None:
        return self.next_processing

    def ensure_aircraft(self, tail_number: str, aircraft_type: str | None = None):
        self.ensure_calls.append((tail_number, aircraft_type))
        return {"id": f"air-{tail_number}"}

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ):
        self.assigned.append((aircraft_id, signature, resolved_format or log_format_id))

    def assign_metadata_for_log_id(
        self,
        log_id: str | None,
        remarks: str | None = None,
        tags: list[str] | None = None,
    ):
        self.metadata_calls.append((log_id, remarks, tags))


class DummyFlyStoVerify(DummyFlySto):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[int] = []

    def resolve_log_for_file(self, filename: str, **kwargs):
        logs_limit = kwargs.get("logs_limit", 250)
        self.calls.append(logs_limit)
        if logs_limit >= 500:
            return f"log-{filename}", f"sig-{filename}", "GenericGpx"
        return None, None, None


def test_extract_crew_assignments_prefers_pic_and_dedupes():
    metadata = {
        "pilots": [
            {"name": "Alex", "role": "Pilot"},
            {"name": "Alex", "role": "PIC"},
            {"name": "Jamie", "role": "Safety pilot"},
        ]
    }
    crew = _extract_crew_assignments(metadata)
    crew_by_name = {entry["name"].lower(): entry for entry in crew}
    assert crew_by_name["alex"]["role"] == "PIC"
    assert crew_by_name["alex"]["is_pic"] is True
    assert crew_by_name["jamie"]["role"] == "Copilot"


def test_extract_crew_assignments_fallback_pilot_fields():
    metadata = {"pilot": "Sam", "co_pilot": ["Dana"]}
    crew = _extract_crew_assignments(metadata)
    names = sorted(entry["name"] for entry in crew)
    assert names == ["Dana", "Sam"]
    assert any(entry["role"] == "PIC" for entry in crew)


def test_tail_number_normalization_candidates():
    tail, aircraft, raw = _normalize_tail_number(["N12345", "Cessna 172", "Unknown"])
    assert tail == "N12345"
    assert aircraft == "Cessna 172"
    assert raw == ["N12345", "Cessna 172", "Unknown"]

    tail, aircraft, raw = _normalize_tail_number("OTHER")
    assert tail is None
    assert aircraft is None
    assert raw == ["OTHER"]

    tail, aircraft, raw = _normalize_tail_number(123)
    assert tail is None
    assert aircraft is None
    assert raw is None


def test_tail_candidate_and_pattern_rules():
    assert _is_tail_candidate("N123") is True
    assert _is_tail_candidate("D-ELI") is True
    assert _matches_tail_pattern("D-ELI") is True
    assert _is_tail_candidate("AB-12345") is True
    assert _matches_tail_pattern("ABC-123") is False
    assert _is_tail_candidate("OTHER") is False


def test_describe_detail_and_kml_detection():
    raw_payload = {
        "flt": {
            "points": [[1, 2], [3, 4]],
            "KML": "<?xml version='1.0'?>",
        }
    }
    points_count, has_kml, schema, preview = _describe_detail(raw_payload, file_path=None)
    assert points_count == 2
    assert has_kml is True
    assert schema
    assert preview
    assert _payload_has_kml(raw_payload["flt"]) is True


def test_build_report_item_enriches_flysto_fields():
    flysto = DummyFlySto()
    flysto.upload_cache["flight.gpx"] = UploadResult(
        signature="sig-1",
        log_id="log-1",
        signature_hash="hash-1",
        log_format="GenericGpx",
    )
    flysto.log_source_cache["log-flight.gpx"] = ("UnknownGarmin", "sys-1")
    detail = FlightDetail(id="F1", raw_payload={}, file_path="/tmp/flight.gpx")

    item = _build_report_item(
        detail=detail,
        status="ok",
        message=None,
        tail_number="N123",
        aircraft_type="C172",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        remarks="ok",
        tags=["cloudahoy"],
        crew=[{"name": "Alex"}],
        flysto=flysto,
    )
    assert item["flysto_upload_signature"] == "sig-1"
    assert item["flysto_upload_signature_hash"] == "hash-1"
    assert item["flysto_upload_log_id"] == "log-1"
    assert item["flysto_log_id"] == "log-flight.gpx"


def test_verify_import_report_retries_with_large_limit(tmp_path: Path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"items": [{"flight_id": "F1", "file_path": "/tmp/F1.gpx"}]})
    )
    flysto = DummyFlyStoVerify()
    flysto.next_processing = 0
    summary = verify_import_report(report_path, flysto)
    payload = json.loads(report_path.read_text())
    assert summary == {"attempted": 1, "resolved": 1, "missing": 0}
    assert payload["items"][0]["flysto_log_id"] == "log-F1.gpx"
    assert 500 in flysto.calls


def test_verify_import_report_reuses_upload_metadata_before_remote_lookup(tmp_path: Path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps({"items": [{"flight_id": "F1", "file_path": "/tmp/F1.gpx"}]})
    )
    flysto = DummyFlySto()
    flysto.upload_cache["F1.gpx"] = UploadResult(
        signature="sig-F1.gpx",
        log_id="log-F1.gpx",
        log_format="GenericGpx",
    )

    summary = verify_import_report(report_path, flysto)
    payload = json.loads(report_path.read_text())

    assert summary == {"attempted": 1, "resolved": 1, "missing": 0}
    assert payload["items"][0]["flysto_log_id"] == "log-F1.gpx"
    assert flysto.resolve_calls == []


def test_reconcile_aircraft_from_report_defaults_unknown_garmin(tmp_path: Path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "flight_id": "F2",
                        "file_path": "/tmp/F2.g3x.csv",
                        "tail_number": "N987",
                        "aircraft_type": "C172",
                    }
                ]
            }
        )
    )
    flysto = DummyFlySto()
    flysto.resolve_sequence = [(None, "sig-2", None)]
    updated = reconcile_aircraft_from_report(report_path, flysto)
    assert updated == 1
    assert flysto.assigned[0][2] == "UnknownGarmin"


def test_reconcile_metadata_updates_only_with_values(tmp_path: Path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "items": [
                    {"flysto_log_id": "log-1", "remarks": "ok", "tags": ["a"]},
                    {"flysto_log_id": "log-2", "remarks": None, "tags": []},
                ]
            }
        )
    )
    flysto = DummyFlySto()
    updated = reconcile_metadata_from_report(report_path, flysto)
    assert updated == 1
    assert flysto.metadata_calls[0][0] == "log-1"


def test_reconcile_metadata_reresolves_stale_log_ids(tmp_path: Path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "flysto_log_id": "log-old",
                        "file_path": "/tmp/flight.g3x.csv",
                        "remarks": "ok",
                        "tags": ["a"],
                    }
                ]
            }
        )
    )

    class DummyFlyStoMetadataRetry(DummyFlySto):
        def assign_metadata_for_log_id(
            self,
            log_id: str | None,
            remarks: str | None = None,
            tags: list[str] | None = None,
        ):
            if log_id == "log-old":
                raise RuntimeError("FlySto log-annotations failed: 404 Log not found")
            super().assign_metadata_for_log_id(log_id, remarks=remarks, tags=tags)

    flysto = DummyFlyStoMetadataRetry()
    flysto.resolve_sequence = [("log-new", "sig-new", "UnknownGarmin")]

    updated = reconcile_metadata_from_report(report_path, flysto)
    payload = json.loads(report_path.read_text())

    assert updated == 1
    assert flysto.metadata_calls[0][0] == "log-new"
    assert payload["items"][0]["flysto_log_id"] == "log-new"
