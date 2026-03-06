"""Additional CLI coverage tests."""
from __future__ import annotations

import argparse
import builtins
from datetime import datetime, timezone
from pathlib import Path
import json
import sys
import types

import pytest

import src.core.cli as cli
from src.core.models import FlightSummary, MigrationResult
from src.core.migration import MigrationStats


class DummyCloudAhoy:
    def __init__(self, *args, **kwargs) -> None:
        return None


class DummyFlySto:
    def __init__(self, *args, **kwargs) -> None:
        self.prepare_result = True
        self.queue = [None]

    def prepare(self) -> bool:
        return self.prepare_result

    def log_files_to_process(self):
        return self.queue.pop(0) if self.queue else 0


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


def test_apply_run_paths_sets_defaults(tmp_path: Path):
    args = argparse.Namespace(
        review_path=None,
        import_report=None,
        exports_dir=None,
        state_path=None,
    )
    run_dir, log_path = cli._apply_run_paths(args, run_id="run-1", runs_dir=str(tmp_path))
    assert run_dir == tmp_path / "run-1"
    assert args.review_path.endswith("review.json")
    assert args.import_report.endswith("import_report.json")
    assert args.exports_dir.endswith("cloudahoy_exports")
    assert args.state_path.endswith("migration.db")
    assert log_path.endswith("docker.log")

    args = argparse.Namespace(
        review_path=None,
        import_report=None,
        exports_dir=None,
        state_path=None,
    )
    run_dir, log_path = cli._apply_run_paths(args, run_id="", runs_dir=str(tmp_path))
    assert run_dir == tmp_path
    assert args.exports_dir == "data/cloudahoy_exports"
    assert args.state_path == "data/migration.db"
    assert log_path == ""


def test_setup_logging_writes_to_file(tmp_path: Path):
    log_path = tmp_path / "logs" / "app.log"
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    class FailingStream:
        def write(self, _data):
            raise RuntimeError("write failed")

        def flush(self):
            raise RuntimeError("flush failed")

    try:
        cli._setup_logging(str(log_path))
        if hasattr(sys.stdout, "_streams"):
            sys.stdout._streams = (*sys.stdout._streams, FailingStream())
        print("hello")
        sys.stderr.write("err")
        sys.stdout.flush()
    finally:
        sys.stdout = original_stdout
        sys.stderr = original_stderr
    content = log_path.read_text()
    assert "hello" in content
    assert "err" in content


def test_date_bound_and_filter_edges():
    dt = cli._parse_date_bound("2026-01-02T01:02:03Z", is_end=False)
    assert dt.tzinfo is not None

    summaries = [
        FlightSummary("A1", datetime(2026, 1, 1), None, None, None),
    ]
    filtered = cli._filter_summaries_by_date(summaries, None, None)
    assert filtered == summaries

    filtered = cli._filter_summaries_by_date(
        summaries,
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        None,
    )
    assert filtered

    summaries = [
        FlightSummary("A2", None, None, None, None),
    ]
    assert cli._filter_summaries_by_date(summaries, datetime(2026, 1, 1, tzinfo=timezone.utc), None) == []


def test_summaries_from_review_invalid_date(tmp_path: Path):
    path = tmp_path / "review.json"
    path.write_text(
        json.dumps({"items": [{"flight_id": "F1", "started_at": "bad"}]})
    )
    summaries = cli._summaries_from_review(path)
    assert summaries[0].started_at is None


def test_prompt_for_missing_env_vars_empty():
    assert cli._prompt_for_missing_env_vars([]) is False


def test_run_review_requires_approval_message(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "prepare_review", lambda **_kwargs: ([], "review-1"))

    exit_code = cli.run([
        "--review-path",
        str(review_path),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_run_config_error_without_prompt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: (_ for _ in ()).throw(cli.ConfigError("Missing required env vars: A")),
    )
    monkeypatch.setattr(cli, "_prompt_for_missing_env_vars", lambda _missing: False)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([])
    assert exit_code == 2


def test_run_config_error_retry_fails(monkeypatch: pytest.MonkeyPatch):
    calls = {"count": 0}

    def fake_load():
        calls["count"] += 1
        raise cli.ConfigError("Missing required env vars: A")

    monkeypatch.setattr(cli, "load_config", fake_load)
    monkeypatch.setattr(cli, "_prompt_for_missing_env_vars", lambda _missing: True)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([])
    assert exit_code == 2


def test_run_flysto_prepare_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    class FailFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.prepare_result = False

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", FailFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
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
    ])
    assert exit_code == 2


def test_run_review_id_missing_uses_provided(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"items": []}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "migrate_flights",
        lambda **_kwargs: ([MigrationResult(flight_id="f1", status="ok")], MigrationStats(1, 1, 0)),
    )

    exit_code = cli.run([
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
    ])
    assert exit_code == 0


def test_run_review_id_missing_manifest_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"items": []}))

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


def test_run_prints_skipped_and_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "migrate_flights",
        lambda **_kwargs: (
            [
                MigrationResult(flight_id="f1", status="skipped", message="dup"),
                MigrationResult(flight_id="f2", status="error", message="boom"),
            ],
            MigrationStats(2, 0, 1),
        ),
    )

    exit_code = cli.run([
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
    ])
    assert exit_code == 1


def test_verify_import_report_returns_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "verify_import_report",
        lambda *_args, **_kwargs: {"missing": 1, "resolved": 0, "attempted": 1},
    )

    exit_code = cli.run([
        "--verify-import-report",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 1


def test_verify_import_report_prepare_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    class FailFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.prepare_result = False

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", FailFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--verify-import-report",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_reconcile_import_report_waits_for_processing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    dummy_flysto = DummyFlySto()
    dummy_flysto.queue = [None]

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", lambda *args, **kwargs: dummy_flysto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(
        cli,
        "verify_import_report",
        lambda *_args, **_kwargs: {"missing": 0, "resolved": 1, "attempted": 1},
    )
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    exit_code = cli.run([
        "--reconcile-import-report",
        "--wait-for-processing",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_reconcile_import_report_prepare_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    class FailFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.prepare_result = False

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", FailFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

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
    ])
    assert exit_code == 2


def test_run_wait_for_processing_unknown_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    class QueueFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.queue = [None]

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", QueueFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "migrate_flights",
        lambda **_kwargs: ([MigrationResult(flight_id="f1", status="ok")], MigrationStats(1, 1, 0)),
    )
    monkeypatch.setattr(cli, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    exit_code = cli.run([
        "--approve-import",
        "--review-id",
        "review-1",
        "--wait-for-processing",
        "--review-path",
        str(review_path),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_run_wait_for_processing_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    class QueueFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.queue = [1, 1]

    counter = {"value": 0.0}

    def fake_monotonic():
        counter["value"] += 1.0
        return counter["value"]

    monkeypatch.setattr(cli.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(cli.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", QueueFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(
        cli,
        "migrate_flights",
        lambda **_kwargs: ([MigrationResult(flight_id="f1", status="ok")], MigrationStats(1, 1, 0)),
    )
    monkeypatch.setattr(cli, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    exit_code = cli.run([
        "--approve-import",
        "--review-id",
        "review-1",
        "--wait-for-processing",
        "--processing-timeout",
        "0.0",
        "--processing-interval",
        "0.0",
        "--review-path",
        str(review_path),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_run_prompt_for_missing_flysto_credentials(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    def config_missing():
        return type(
            "Config",
            (),
            {
                "dry_run": False,
                "max_flights": None,
                "flysto_session_cookie": None,
                "flysto_email": None,
                "flysto_password": None,
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

    monkeypatch.setattr(cli, "load_config", config_missing)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "_prompt_for_missing_env_vars", lambda _missing: False)
    monkeypatch.setattr(cli, "prepare_review", lambda **_kwargs: ([], "review-1"))

    exit_code = cli.run([
        "--review",
        "--review-path",
        str(review_path),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_run_prompt_for_missing_flysto_retry_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))
    calls = {"count": 0}

    def load_config():
        calls["count"] += 1
        if calls["count"] > 1:
            raise cli.ConfigError("Missing required env vars: FLYSTO_EMAIL")
        return type(
            "Config",
            (),
            {
                "dry_run": False,
                "max_flights": None,
                "flysto_session_cookie": None,
                "flysto_email": None,
                "flysto_password": None,
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

    monkeypatch.setattr(cli, "load_config", load_config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "_prompt_for_missing_env_vars", lambda _missing: True)

    exit_code = cli.run([
        "--review",
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


def test_run_progress_without_verbose(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    review_path = tmp_path / "review.json"
    review_path.write_text(json.dumps({"review_id": "review-1", "items": []}))

    def fake_migrate(**kwargs):
        progress = kwargs.get("progress")
        if progress:
            progress("flysto_upload_done", {"flight_id": "F1"})
        return [MigrationResult(flight_id="f1", status="ok")], MigrationStats(1, 1, 0)

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "migrate_flights", fake_migrate)

    exit_code = cli.run([
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
    ])
    assert exit_code == 0


def test_run_filters_summaries_by_date(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    summaries = [
        FlightSummary("A1", datetime(2026, 1, 1, tzinfo=timezone.utc), None, None, None),
        FlightSummary("A2", datetime(2026, 1, 2, tzinfo=timezone.utc), None, None, None),
    ]

    class CloudAhoyDates:
        def __init__(self, *args, **kwargs):
            return None

        def list_flights(self, limit=None):
            return summaries

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", CloudAhoyDates)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "prepare_review", lambda **_kwargs: ([], "review-1"))

    exit_code = cli.run([
        "--review",
        "--start-date",
        "2026-01-02",
        "--end-date",
        "2026-01-02",
        "--max-flights",
        "1",
        "--review-path",
        str(tmp_path / "review.json"),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0


def test_guided_keyboard_interrupt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    rich_mod = types.ModuleType("rich")
    console_mod = types.ModuleType("rich.console")
    guided_mod = types.ModuleType("src.core.guided")

    class DummyConsole:
        def __init__(self, *args, **kwargs):
            return None

    console_mod.Console = DummyConsole

    def fake_run_guided(**_kwargs):
        raise KeyboardInterrupt

    guided_mod.run_guided = fake_run_guided

    monkeypatch.setitem(sys.modules, "rich", rich_mod)
    monkeypatch.setitem(sys.modules, "rich.console", console_mod)
    monkeypatch.setitem(sys.modules, "src.core.guided", guided_mod)

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    exit_code = cli.run([
        "--guided",
        "--review-path",
        str(tmp_path / "review.json"),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 130


def test_guided_missing_rich(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    original_import = __import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("rich"):
            raise ModuleNotFoundError("no rich")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--guided",
        "--review-path",
        str(tmp_path / "review.json"),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_guided_load_failed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    guided_mod = types.ModuleType("src.core.guided")
    monkeypatch.setitem(sys.modules, "src.core.guided", guided_mod)
    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--guided",
        "--review-path",
        str(tmp_path / "review.json"),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_guided_requires_api_clients(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    class CloudB:
        pass

    class CloudA:
        def __init__(self, *args, **kwargs):
            cli.CloudAhoyClient = CloudB

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", CloudA)
    monkeypatch.setattr(cli, "FlyStoClient", DummyFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--guided",
        "--review-path",
        str(tmp_path / "review.json"),
        "--import-report",
        str(tmp_path / "report.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_verify_import_report_prepare_failure_with_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    class FailFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.prepare_result = False

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", FailFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--verify-import-report",
        "--dry-run",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_reconcile_import_report_prepare_failure_with_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    class FailFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.prepare_result = False

    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", FailFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())

    exit_code = cli.run([
        "--reconcile-import-report",
        "--dry-run",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 2


def test_reconcile_import_report_wait_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    report_path = tmp_path / "report.json"
    report_path.write_text(json.dumps({"items": []}))

    class QueueFlySto(DummyFlySto):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.queue = [1, 1]

    counter = {"value": 0.0}

    def fake_monotonic():
        counter["value"] += 1.0
        return counter["value"]

    monkeypatch.setattr(cli.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(cli.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(cli, "load_config", _config)
    monkeypatch.setattr(cli, "CloudAhoyClient", DummyCloudAhoy)
    monkeypatch.setattr(cli, "FlyStoClient", QueueFlySto)
    monkeypatch.setattr(cli, "MigrationState", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(cli, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(cli, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_crew_from_report", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(cli, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 0)

    exit_code = cli.run([
        "--reconcile-import-report",
        "--wait-for-processing",
        "--processing-timeout",
        "0.0",
        "--processing-interval",
        "0.0",
        "--import-report",
        str(report_path),
        "--review-path",
        str(tmp_path / "review.json"),
        "--exports-dir",
        str(tmp_path / "exports"),
        "--state-path",
        str(tmp_path / "state.db"),
    ])
    assert exit_code == 0
