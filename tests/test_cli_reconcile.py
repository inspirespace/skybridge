"""Tests for CLI reconcile flows."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.config import Config
import src.core.cli as cli


class DummyCloudAhoy:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def list_flights(self, limit=None):
        return []


class DummyFlySto:
    def __init__(self, *args, **kwargs) -> None:
        self._queue = [1, 0]

    def prepare(self) -> bool:
        return True

    def log_files_to_process(self):
        return self._queue.pop(0) if self._queue else 0


def _config() -> Config:
    return Config(
        cloudahoy_api_key=None,
        cloudahoy_base_url="https://cloudahoy",
        cloudahoy_email="user",
        cloudahoy_password="pass",
        cloudahoy_web_base_url="https://cloudahoy",
        cloudahoy_flights_url=None,
        cloudahoy_export_url_template=None,
        flysto_api_key=None,
        flysto_base_url="https://flysto",
        flysto_email="user",
        flysto_password="pass",
        flysto_web_base_url="https://flysto",
        flysto_upload_url=None,
        flysto_session_cookie="cookie",
        flysto_log_upload_url=None,
        flysto_include_metadata=False,
        flysto_min_request_interval=0.01,
        flysto_max_request_retries=2,
        cloudahoy_export_format="g3x",
        cloudahoy_export_formats=["g3x", "gpx"],
        mode="api",
        headless=True,
        dry_run=False,
        max_flights=None,
    )


def test_reconcile_import_report_flow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reconcile flow should run verify and reconcile calls."""
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"results": []}))

    monkeypatch.setattr(cli, "load_config", lambda: _config())
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)

    monkeypatch.setattr(cli, "verify_import_report", lambda *args, **kwargs: {"missing": 0})
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *args, **kwargs: 1)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *args, **kwargs: 2)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *args, **kwargs: 3)

    exit_code = cli.run([
        "--reconcile-import-report",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
        "--wait-for-processing",
        "--processing-interval",
        "0.01",
        "--processing-timeout",
        "1",
    ])

    assert exit_code == 0
