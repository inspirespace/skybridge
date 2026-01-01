from __future__ import annotations

import json
import shutil
from pathlib import Path

from src.core.migration import (
    reconcile_aircraft_from_report,
    reconcile_crew_from_report,
    reconcile_metadata_from_report,
)


class DummyFlyStoFixture:
    def __init__(self, filename_to_log_id: dict[str, str]) -> None:
        self._filename_to_log_id = filename_to_log_id
        self.assigned_aircraft: list[tuple[str | None, str | None]] = []
        self.assigned_crew: list[str] = []
        self.assigned_metadata: list[str] = []

    def resolve_log_for_file(self, filename: str, **_kwargs):
        log_id = self._filename_to_log_id.get(filename)
        return log_id, f"sig-{filename}", "UnknownGarmin"

    def resolve_log_source_for_log_id(self, log_id: str, include_annotations: bool = True):
        return None, None

    def ensure_aircraft(self, tail_number, aircraft_type=None):
        return {"id": f"aircraft-{tail_number}"}

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


def test_reconcile_from_run_fixture(tmp_path: Path):
    fixture_dir = Path("tests/fixtures/run-20251228T185601Z")
    report_src = fixture_dir / "import_report.json"
    review_src = fixture_dir / "review.json"
    assert report_src.core.exists()
    assert review_src.core.exists()

    report_path = tmp_path / "import_report.json"
    review_path = tmp_path / "review.json"
    shutil.copy(report_src, report_path)
    shutil.copy(review_src, review_path)

    payload = json.loads(report_path.read_text())
    items = [item for item in payload.get("items", []) if isinstance(item, dict)]
    filename_to_log_id = {
        Path(item["file_path"]).name: item["flysto_log_id"]
        for item in items
        if item.get("file_path") and item.get("flysto_log_id")
    }
    flysto = DummyFlyStoFixture(filename_to_log_id)

    reconciled_aircraft = reconcile_aircraft_from_report(report_path, flysto)
    reconciled_crew = reconcile_crew_from_report(
        report_path,
        flysto,
        review_path=review_path,
    )
    reconciled_metadata = reconcile_metadata_from_report(report_path, flysto)

    assert reconciled_aircraft == len(items)
    assert reconciled_crew == len(items)
    assert reconciled_metadata == len(items)
    assert len(flysto.assigned_aircraft) == len(items)
    assert len(flysto.assigned_crew) == len(items)
    assert len(flysto.assigned_metadata) == len(items)
