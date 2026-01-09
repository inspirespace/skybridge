"""Tests for guided helpers."""
from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console

import src.core.guided as guided
from src.core.models import FlightSummary


def test_summarize_review(tmp_path: Path) -> None:
    payload = {
        "items": [
            {"flight_id": "f1", "tail_number": "N123", "started_at": "2026-01-01T10:00:00Z"},
            {"flight_id": "f2", "tail_number": "N123", "started_at": "2026-01-02T10:00:00Z"},
        ]
    }
    path = tmp_path / "review.json"
    path.write_text(json.dumps(payload))
    summary = guided._summarize_review(path)
    assert summary["count"] == 2
    assert summary["tails"]["N123"] == 2


def test_write_guided_summary(tmp_path: Path) -> None:
    options = guided.GuidedOptions(
        max_flights=5,
        force=False,
        wait_for_processing=True,
        verify_after_import=True,
        reconcile_after_import=False,
        run_id="run-1",
        export_formats="g3x,gpx",
        start_date=None,
        end_date=None,
    )
    guided._write_guided_summary(tmp_path, options, "review-1", {"count": 0})
    payload = json.loads((tmp_path / "guided.json").read_text())
    assert payload["run_id"] == "run-1"


def test_progress_callback_logs() -> None:
    console = Console(file=open(Path("/dev/null"), "w"))
    progress = guided._build_progress(console, total=1)
    handler = guided._progress_callback(progress, 1, console)
    handler("flysto_processing_queue", {"n_files": 3})
