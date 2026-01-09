"""CLI progress and wait-for-processing coverage tests."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

import src.core.cli as cli
from src.core.migration import MigrationStats
from src.core.models import MigrationResult


class DummyCloudAhoy:
    def __init__(self, *args, **kwargs) -> None:
        return None


class DummyFlySto:
    def __init__(self, *args, **kwargs) -> None:
        self.queue = [2, 0]

    def prepare(self) -> bool:
        return True

    def log_files_to_process(self):
        if self.queue:
            return self.queue.pop(0)
        return 0


def _config():
    return type(
        "Config",
        (),
        {
            "dry_run": False,
            "max_flights": None,
            "flysto_session_cookie": "cookie",
            "flysto_email": "user",
            "flysto_password": "pass",
            "cloudahoy_api_key": "key",
            "cloudahoy_base_url": "https://example.test",
            "cloudahoy_email": "email",
            "cloudahoy_password": "pass",
            "cloudahoy_export_format": None,
            "cloudahoy_export_formats": None,
            "flysto_api_key": None,
            "flysto_base_url": "https://example.test",
            "flysto_log_upload_url": None,
            "flysto_include_metadata": True,
            "flysto_api_version": None,
            "flysto_min_request_interval": 0,
            "flysto_max_request_retries": 1,
        },
    )()


def test_run_verbose_progress_and_wait_for_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "review_id": "review-1",
                "items": [
                    {"flight_id": "F1", "started_at": "2026-01-01T10:00:00Z"}
                ],
            }
        )
    )

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli.time, "sleep", lambda _seconds: None)

    def fake_migrate_flights(*, progress=None, **_kwargs):
        if progress:
            progress("start", {"flight_id": "F1"})
            progress("cloudahoy_fetch_start", {"flight_id": "F1"})
            progress("cloudahoy_fetch_done", {"flight_id": "F1", "file_path": "f1.gpx"})
            progress("flysto_upload_start", {"flight_id": "F1"})
            progress("flysto_upload_done", {"flight_id": "F1"})
            progress("flysto_assign_aircraft_file_start", {"flight_id": "F1", "aircraft_id": "a1"})
            progress("flysto_assign_aircraft_file_done", {"flight_id": "F1", "aircraft_id": "a1"})
            progress("flysto_assign_crew_start", {"flight_id": "F1", "crew_count": 1})
            progress("flysto_assign_crew_done", {"flight_id": "F1", "crew_count": 1})
            progress("flysto_assign_metadata_start", {"flight_id": "F1", "has_remarks": True, "tag_count": 2})
            progress("flysto_assign_metadata_done", {"flight_id": "F1", "has_remarks": True, "tag_count": 2})
            progress("flysto_assign_aircraft_group", {"tail_number": "N123", "aircraft_id": "a1"})
            progress("flysto_processing_queue", {"n_files": 2})
            progress("end", {"flight_id": "F1", "status": "ok", "message": None})
        results = [MigrationResult(flight_id="F1", status="ok")]
        stats = MigrationStats(attempted=1, succeeded=1, failed=0)
        return results, stats

    monkeypatch.setattr(cli, "migrate_flights", fake_migrate_flights)
    monkeypatch.setattr(cli, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0, "resolved": 1, "attempted": 1})
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 1)

    exit_code = cli.run(
        [
            "--approve-import",
            "--review-id",
            "review-1",
            "--review-path",
            str(review_path),
            "--import-report",
            str(tmp_path / "report.json"),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--state-path",
            str(tmp_path / "state.db"),
            "--verbose",
            "--wait-for-processing",
            "--processing-interval",
            "0",
        ]
    )
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "FlySto upload" in output
    assert "Verify summary" in output


def test_progress_missing_step_does_not_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    def fake_migrate_flights(*, progress=None, **_kwargs):
        if progress:
            progress("flysto_upload_done", {"flight_id": "F1"})
        results = [MigrationResult(flight_id="F1", status="ok")]
        stats = MigrationStats(attempted=1, succeeded=1, failed=0)
        return results, stats

    monkeypatch.setattr(cli, "migrate_flights", fake_migrate_flights)

    exit_code = cli.run(
        [
            "--approve-import",
            "--review-id",
            "review-1",
            "--review-path",
            str(review_path),
            "--import-report",
            str(tmp_path / "report.json"),
            "--exports-dir",
            str(tmp_path / "exports"),
            "--state-path",
            str(tmp_path / "state.db"),
            "--verbose",
        ]
    )
    assert exit_code == 0
