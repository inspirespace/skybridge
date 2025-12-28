from __future__ import annotations

import json
from pathlib import Path

from src.migration import (
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
    verify_import_report,
)
from src.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class DummyFlyStoReports(FlyStoClient):
    def __init__(self) -> None:
        super().__init__(api_key="", base_url="https://example.test")
        self.assigned_aircraft: list[tuple[str | None, str | None]] = []
        self.assigned_crew: list[str] = []
        self.assigned_metadata: list[str] = []
        self._log_lookup_calls = 0

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        if url.endswith("/api/log-list"):
            return DummyResponse(text=json.dumps(["log-1"]))
        if url.endswith("/api/log-summary"):
            payload = {
                "items": [
                    {
                        "id": "log-1",
                        "summary": {
                            "data": {
                                "t3": [{"file": "flight.g3x.csv", "format": "UnknownGarmin"}],
                                "6h": "SIGVALUE",
                            }
                        },
                    }
                ]
            }
            return DummyResponse(text=json.dumps(payload))
        if "/api/log-metadata" in url:
            payload = {
                "items": [{"id": "log-1", "aircraft": 0, "annotations": {"tags": ["cloudahoy"]}}],
                "aircraft": [{"avionics": {"logFormatId": "UnknownGarmin", "systemId": "system id: D-KBUH"}}],
            }
            return DummyResponse(text=json.dumps(payload))
        return DummyResponse(text="{}")

    def ensure_aircraft(self, tail_number, aircraft_type=None):
        return {"id": "aircraft-1"}

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ) -> None:
        self.assigned_aircraft.append((signature, resolved_format))

    def assign_crew_for_log_id(self, log_id: str | None, crew):
        if log_id:
            self.assigned_crew.append(log_id)

    def assign_metadata_for_log_id(self, log_id: str | None, remarks=None, tags=None):
        if log_id:
            self.assigned_metadata.append(log_id)

    def fetch_log_metadata(self, log_id: str, annotations: str = "crew,tags,remarks"):
        return {"items": [{"id": log_id, "annotations": {"crew": [[1, -6]]}}]}


def _write_report(path: Path) -> None:
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "tail_number": "D-KBUH",
                "aircraft_type": "WT9",
                "file_path": str(path.parent / "flight.g3x.csv"),
                "remarks": "notes",
                "tags": ["cloudahoy"],
                "crew": [{"name": "Alex", "role": "Student", "is_pic": False}],
                "flysto_log_id": "log-1",
                "flysto_signature": "sig",
                "flysto_format": "UnknownGarmin",
                "flysto_upload_signature_hash": "hash123",
                "flysto_upload_format": "UnknownGarmin",
            }
        ]
    }
    path.write_text(json.dumps(payload))


def test_verify_and_reconcile_report(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    _write_report(report_path)

    flysto = DummyFlyStoReports()

    summary = verify_import_report(report_path, flysto)
    assert summary["resolved"] == 1

    reconciled_aircraft = reconcile_aircraft_from_report(report_path, flysto)
    reconciled_crew = reconcile_crew_from_report(report_path, flysto)
    reconciled_metadata = reconcile_metadata_from_report(report_path, flysto)

    assert reconciled_aircraft == 1
    assert reconciled_crew == 1
    assert reconciled_metadata == 1
    assert flysto.assigned_aircraft == [("system id: D-KBUH", "UnknownGarmin")]
    assert flysto.assigned_crew == ["log-1"]
    assert flysto.assigned_metadata == ["log-1"]
