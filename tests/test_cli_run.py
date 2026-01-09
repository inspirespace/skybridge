"""Tests for CLI run flow."""
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
        pass

    def prepare(self) -> bool:
        return True

    def log_files_to_process(self):
        return 0


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
        flysto_api_version=None,
        flysto_min_request_interval=0.01,
        flysto_max_request_retries=2,
        cloudahoy_export_format="g3x",
        cloudahoy_export_formats=["g3x", "gpx"],
        mode="api",
        headless=True,
        dry_run=False,
        max_flights=None,
    )


def test_review_run_writes_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review mode should call prepare_review and return 0."""
    review_path = tmp_path / "review.json"

    monkeypatch.setattr(cli, "load_config", lambda: _config())
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)

    def fake_prepare_review(**kwargs):
        kwargs["output_path"].write_text(json.dumps({"review_id": "review-123"}))
        return [], "review-123"

    monkeypatch.setattr(cli, "prepare_review", fake_prepare_review)

    exit_code = cli.run([
        "--review",
        "--review-path",
        str(review_path),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])

    assert exit_code == 0
    assert review_path.exists()


def test_verify_import_report_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify flow should fail when import report is missing."""
    report_path = tmp_path / "missing.json"

    monkeypatch.setattr(cli, "load_config", lambda: _config())
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)

    exit_code = cli.run([
        "--verify-import-report",
        "--import-report",
        str(report_path),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])

    assert exit_code == 2


def test_approve_import_review_id_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Approve import should fail if review id mismatches manifest."""
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "expected"}))

    monkeypatch.setattr(cli, "load_config", lambda: _config())
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)

    exit_code = cli.run([
        "--approve-import",
        "--review-id",
        "different",
        "--review-path",
        str(review_path),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])

    assert exit_code == 2
