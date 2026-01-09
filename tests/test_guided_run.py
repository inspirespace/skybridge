"""tests/test_guided_run.py module."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rich.console import Console

import src.core.guided as guided
from src.core.models import FlightSummary


class DummyCloudAhoy:
    def __init__(self):
        self.exports_dir = None
        self.export_formats = None
        self.calls = []

    def list_flights(self, limit=None):
        self.calls.append(("list", limit))
        return [
            FlightSummary("f1", datetime(2026, 1, 1, tzinfo=timezone.utc), None, None, None),
            FlightSummary("f2", datetime(2026, 1, 2, tzinfo=timezone.utc), None, None, None),
        ]


class DummyFlySto:
    def __init__(self, queue_values=None):
        self.queue_values = queue_values or []
        self.prepare_calls = 0

    def prepare(self):
        self.prepare_calls += 1
        return True

    def log_files_to_process(self):
        return self.queue_values.pop(0) if self.queue_values else 0


@dataclass
class DummyStats:
    attempted: int
    succeeded: int
    failed: int


def test_parse_started_at_invalid():
    assert guided._parse_started_at("bad") is None
    assert guided._parse_started_at(None) is None


def test_summaries_from_review(tmp_path: Path):
    payload = {
        "items": [
            {"flight_id": "f1", "started_at": "2026-01-01T00:00:00Z"},
            {"flight_id": ""},
            "bad",
        ]
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(payload))
    summaries = guided._summaries_from_review(path)
    assert [s.id for s in summaries] == ["f1"]


def test_preflight_checks_success():
    console = Console(file=io.StringIO())
    cloudahoy = DummyCloudAhoy()
    flysto = DummyFlySto()
    assert guided._preflight_checks(console, cloudahoy, flysto) is True


def test_run_guided_happy_path(tmp_path: Path, monkeypatch):
    console = Console(file=io.StringIO())
    cloudahoy = DummyCloudAhoy()
    flysto = DummyFlySto()
    run_dir = tmp_path / "runs" / "run-1"

    options = guided.GuidedOptions(
        max_flights=1,
        force=False,
        wait_for_processing=False,
        verify_after_import=False,
        reconcile_after_import=False,
        run_id="run-1",
        export_formats="gpx",
    )

    monkeypatch.setattr(guided, "_prompt_guided_options", lambda *_args, **_kwargs: options)
    monkeypatch.setattr(guided.Confirm, "ask", lambda *_args, **_kwargs: True)

    def fake_prepare_review(*, output_path: Path, **_kwargs):
        payload = {
            "items": [
                {
                    "flight_id": "f1",
                    "started_at": "2026-01-01T00:00:00Z",
                    "duration_seconds": 10,
                }
            ]
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload))
        return payload, "review-1"

    def fake_migrate_flights(*_args, **_kwargs):
        report_path = _kwargs.get("report_path")
        if report_path:
            Path(report_path).write_text(json.dumps({"items": []}))
        return [], DummyStats(attempted=1, succeeded=1, failed=0)

    monkeypatch.setattr(guided, "prepare_review", fake_prepare_review)
    monkeypatch.setattr(guided, "migrate_flights", fake_migrate_flights)

    result = guided.run_guided(
        console=console,
        cloudahoy=cloudahoy,
        flysto=flysto,
        state=guided.MigrationState(tmp_path / "state.db"),
        run_dir=run_dir,
        review_path=run_dir / "review.json",
        report_path=run_dir / "import_report.json",
        exports_dir=run_dir / "cloudahoy_exports",
        summaries=None,
        max_flights=1,
        force=False,
        processing_interval=0.0,
        processing_timeout=0.0,
        run_id="run-1",
    )

    assert result == 0
    assert (tmp_path / "runs" / "run-1" / "review.json").exists()
    assert (tmp_path / "runs" / "run-1" / "guided.json").exists()


def test_run_guided_aborts_on_preflight(tmp_path: Path, monkeypatch):
    console = Console(file=io.StringIO())
    cloudahoy = DummyCloudAhoy()
    flysto = DummyFlySto()

    monkeypatch.setattr(guided, "_preflight_checks", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(guided.Confirm, "ask", lambda *_args, **_kwargs: False)
    result = guided.run_guided(
        console=console,
        cloudahoy=cloudahoy,
        flysto=flysto,
        state=guided.MigrationState(tmp_path / "state.db"),
        run_dir=tmp_path / "run",
        review_path=tmp_path / "run" / "review.json",
        report_path=tmp_path / "run" / "report.json",
        exports_dir=tmp_path / "run" / "exports",
        summaries=None,
        max_flights=1,
        force=False,
        processing_interval=0.0,
        processing_timeout=0.0,
        run_id="run-1",
    )
    assert result == 1


def test_run_guided_wait_verify_reconcile(tmp_path: Path, monkeypatch):
    console = Console(file=io.StringIO())
    cloudahoy = DummyCloudAhoy()
    flysto = DummyFlySto(queue_values=[2, 0, 1, 0])
    run_dir = tmp_path / "runs" / "run-2"

    options = guided.GuidedOptions(
        max_flights=1,
        force=False,
        wait_for_processing=True,
        verify_after_import=True,
        reconcile_after_import=True,
        run_id="run-2",
        export_formats="gpx",
        start_date="2026-01-01",
        end_date="2026-01-02",
    )

    monkeypatch.setattr(guided, "_prompt_guided_options", lambda *_args, **_kwargs: options)
    monkeypatch.setattr(guided.Confirm, "ask", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(guided, "verify_import_report", lambda *_args, **_kwargs: {"missing": 0})
    monkeypatch.setattr(guided, "reconcile_aircraft_from_report", lambda *_args, **_kwargs: 1)
    monkeypatch.setattr(guided, "reconcile_crew_from_report", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(guided, "reconcile_metadata_from_report", lambda *_args, **_kwargs: 3)

    def fake_prepare_review(*, output_path: Path, **_kwargs):
        payload = {
            "items": [
                {
                    "flight_id": "f1",
                    "started_at": "2026-01-01T00:00:00Z",
                    "duration_seconds": 10,
                }
            ]
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload))
        return payload, "review-2"

    def fake_migrate_flights(*_args, **_kwargs):
        report_path = _kwargs.get("report_path")
        if report_path:
            Path(report_path).write_text(json.dumps({"items": []}))
        return [], DummyStats(attempted=1, succeeded=0, failed=1)

    monotonic_values = iter([0.0, 10.0, 0.0, 10.0])
    monkeypatch.setattr(guided.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(guided.time, "sleep", lambda _sec: None)
    monkeypatch.setattr(guided, "prepare_review", fake_prepare_review)
    monkeypatch.setattr(guided, "migrate_flights", fake_migrate_flights)

    result = guided.run_guided(
        console=console,
        cloudahoy=cloudahoy,
        flysto=flysto,
        state=guided.MigrationState(tmp_path / "state.db"),
        run_dir=run_dir,
        review_path=run_dir / "review.json",
        report_path=run_dir / "import_report.json",
        exports_dir=run_dir / "cloudahoy_exports",
        summaries=None,
        max_flights=1,
        force=False,
        processing_interval=0.0,
        processing_timeout=0.0,
        run_id="run-2",
        setup_logging=lambda _path: None,
    )

    assert result == 0
