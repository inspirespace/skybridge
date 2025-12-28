from __future__ import annotations

import json
from pathlib import Path

from src.migration import reconcile_crew_from_report


class DummyFlySto:
    def __init__(self) -> None:
        self.assigned: list[str] = []
        self.fetch_calls = 0

    def resolve_log_for_file(self, filename: str, **_kwargs):
        return "log-new", None, None

    def assign_crew_for_log_id(self, log_id: str | None, crew):
        if log_id:
            self.assigned.append(log_id)

    def fetch_log_metadata(self, log_id: str):
        self.fetch_calls += 1
        if self.fetch_calls == 1:
            return {"items": [{"id": log_id, "annotations": {}}]}
        return {"items": [{"id": log_id, "annotations": {"crew": [[1, -6]]}}]}


def test_reconcile_crew_resolves_and_retries(monkeypatch, tmp_path: Path):
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
    monkeypatch.setattr("src.migration.time.sleep", lambda _seconds: None)

    updated = reconcile_crew_from_report(report_path, dummy)

    assert updated == 1
    assert dummy.assigned == ["log-new", "log-new"]
    updated_payload = json.loads(report_path.read_text())
    assert updated_payload["items"][0]["flysto_log_id"] == "log-new"
