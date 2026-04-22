"""tests/test_migration_reconcile.py module."""
from __future__ import annotations

import json
from pathlib import Path

from src.core.migration import (
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
)


class DummyFlySto:
    def __init__(self) -> None:
        """Internal helper for init  ."""
        self.assigned: list[str] = []
        self.fetch_calls = 0

    def resolve_log_for_file(self, filename: str, **_kwargs):
        """Handle resolve log for file."""
        return "log-new", None, None

    def assign_crew_for_log_id(self, log_id: str | None, crew):
        """Handle assign crew for log id."""
        if log_id:
            self.assigned.append(log_id)

    def fetch_log_metadata(self, log_id: str):
        """Handle fetch log metadata."""
        self.fetch_calls += 1
        if self.fetch_calls == 1:
            return {"items": [{"id": log_id, "annotations": {}}]}
        return {"items": [{"id": log_id, "annotations": {"crew": [[1, -6]]}}]}


def test_reconcile_crew_resolves_and_retries(monkeypatch, tmp_path: Path):
    """Test reconcile crew resolves and retries."""
    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "flysto_log_id": "log-old",
                "file_path": str(tmp_path / "flight.g3x.csv"),
                "crew": [{"name": "Alex", "role": "Student", "is_pic": False}],
            }
        ]
    }
    report_path.write_text(json.dumps(payload))

    dummy = DummyFlySto()
    monkeypatch.setattr("src.core.migration.time.sleep", lambda _seconds: None)

    updated = reconcile_crew_from_report(report_path, dummy)

    assert updated == 1
    assert dummy.assigned == ["log-new", "log-new"]
    updated_payload = json.loads(report_path.read_text())
    assert updated_payload["items"][0]["flysto_log_id"] == "log-new"


class _HeartbeatFlySto:
    """Minimal FlySto stub for heartbeat coverage tests."""

    def resolve_log_for_file(self, *_args, **_kwargs):
        return None, None, None

    def assign_crew_for_log_id(self, *_args, **_kwargs):
        return None

    def fetch_log_metadata(self, *_args, **_kwargs):
        return {"items": []}

    def resolve_log_source_for_log_id(self, *_args, **_kwargs):
        return None, None

    def ensure_aircraft(self, *_args, **_kwargs):
        return None

    def assign_aircraft_for_signature(self, *_args, **_kwargs):
        return None

    def log_files_to_process(self):
        return 0


def test_reconcile_functions_invoke_heartbeat_per_item(tmp_path: Path):
    report_path = tmp_path / "import_report.json"
    payload = {
        "items": [
            {"flight_id": "f-1", "file_path": str(tmp_path / "a.csv"), "tail_number": "N1"},
            {"flight_id": "f-2", "file_path": str(tmp_path / "b.csv"), "tail_number": "N2"},
            {"flight_id": "f-3", "file_path": str(tmp_path / "c.csv"), "tail_number": "N3"},
        ]
    }
    report_path.write_text(json.dumps(payload))
    flysto = _HeartbeatFlySto()

    for fn in (reconcile_aircraft_from_report, reconcile_metadata_from_report):
        calls = {"n": 0}

        def heartbeat() -> None:
            calls["n"] += 1

        fn(report_path, flysto, heartbeat=heartbeat)
        assert calls["n"] >= 3

    crew_calls = {"n": 0}

    def crew_heartbeat() -> None:
        crew_calls["n"] += 1

    reconcile_crew_from_report(report_path, flysto, heartbeat=crew_heartbeat)
    assert crew_calls["n"] >= 3


def test_reconcile_shared_payload_skips_disk_writes(tmp_path: Path, monkeypatch):
    report_path = tmp_path / "import_report.json"
    initial = {
        "items": [
            {"flight_id": "f-1", "file_path": str(tmp_path / "a.csv"), "tail_number": "N1"},
        ]
    }
    report_path.write_text(json.dumps(initial))
    original_mtime = report_path.stat().st_mtime_ns

    flysto = _HeartbeatFlySto()
    shared = json.loads(report_path.read_text())

    reconcile_aircraft_from_report(report_path, flysto, payload=shared)
    reconcile_crew_from_report(report_path, flysto, payload=shared)
    reconcile_metadata_from_report(report_path, flysto, payload=shared)

    # Shared payload path should not rewrite the report on disk.
    assert report_path.stat().st_mtime_ns == original_mtime
    # The passed-in dict is mutated in place.
    assert "aircraft_reconciled_at" in shared
    assert "metadata_reconciled_at" in shared
