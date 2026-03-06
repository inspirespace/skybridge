"""Extra CLI helper coverage tests."""
from __future__ import annotations

from pathlib import Path
import json

import pytest

import src.core.cli as cli


class DummyCloudAhoy:
    def __init__(self, *args, **kwargs) -> None:
        return None


class DummyFlySto:
    def __init__(self, *args, **kwargs) -> None:
        self.prepare_calls = 0

    def prepare(self) -> bool:
        self.prepare_calls += 1
        return True


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
            "flysto_min_request_interval": 0,
            "flysto_max_request_retries": 1,
        },
    )()


def test_read_review_id_handles_missing_and_invalid(tmp_path: Path):
    path = tmp_path / "review.json"
    assert cli._read_review_id(path) is None
    path.write_text("{not json}")
    assert cli._read_review_id(path) is None
    path.write_text(json.dumps({"review_id": "abc"}))
    assert cli._read_review_id(path) == "abc"


def test_summaries_from_review_filters_and_parses(tmp_path: Path):
    payload = {
        "items": [
            {"flight_id": "F1", "started_at": "2026-01-01T10:00:00Z"},
            {"flight_id": "", "started_at": "2026-01-01T10:00:00Z"},
            "bad",
        ]
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(payload))
    summaries = cli._summaries_from_review(path)
    assert len(summaries) == 1
    assert summaries[0].id == "F1"
    assert summaries[0].started_at is not None


def test_parse_missing_env_vars():
    err = cli.ConfigError("Missing required env vars: A, B")
    assert cli._parse_missing_env_vars(err) == ["A", "B"]
    err2 = cli.ConfigError("Other error")
    assert cli._parse_missing_env_vars(err2) == []


def test_prompt_for_missing_env_vars(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(cli, "_prompt_env_var", lambda name: "value" if name == "A" else "")
    assert cli._prompt_for_missing_env_vars(["A", "B"]) is True
    assert cli.os.environ.get("A") == "value"


def test_run_rejects_mismatched_review_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "abc"}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--approve-import",
        "--review-id",
        "xyz",
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


def test_run_requires_review_id_when_approving(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "abc"}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--approve-import",
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
