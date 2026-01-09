"""Extra guided helper coverage tests."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import io
import json

import pytest
from rich.console import Console

import src.core.guided as guided
from src.core.models import FlightSummary


def test_summarize_review_and_render(tmp_path: Path):
    review_path = tmp_path / "review.json"
    review_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "flight_id": "F1",
                        "tail_number": "N123",
                        "started_at": "2026-01-01T10:00:00Z",
                    },
                    "bad",
                ]
            }
        )
    )
    summary = guided._summarize_review(review_path)
    assert summary["count"] == 2
    assert summary["tails"]["N123"] == 1

    console = Console(file=io.StringIO())
    guided._render_review_summary(console, summary)

    empty_summary = {"count": 0, "min_date": None, "max_date": None, "tails": Counter()}
    guided._render_review_summary(console, empty_summary)


def test_write_guided_summary(tmp_path: Path):
    options = guided.GuidedOptions(
        max_flights=5,
        force=False,
        wait_for_processing=True,
        verify_after_import=True,
        reconcile_after_import=True,
        run_id="run-1",
        export_formats="gpx",
        start_date="2026-01-01",
        end_date="2026-01-02",
    )
    summary = {
        "count": 1,
        "min_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "max_date": datetime(2026, 1, 2, tzinfo=timezone.utc),
        "tails": Counter({"N123": 1}),
    }
    guided._write_guided_summary(tmp_path, options, "review-1", summary)
    payload = json.loads((tmp_path / "guided.json").read_text())
    assert payload["review_id"] == "review-1"
    assert payload["review_summary"]["tails"]["N123"] == 1


def test_prompt_guided_options(monkeypatch: pytest.MonkeyPatch):
    console = Console(file=io.StringIO())
    monkeypatch.setattr(guided.IntPrompt, "ask", lambda *_args, **_kwargs: 2)
    monkeypatch.setattr(guided.Confirm, "ask", lambda *_args, **_kwargs: True)

    responses = iter(["2026-01-01", "", "gpx"])

    def fake_prompt(*_args, **_kwargs):
        return next(responses)

    monkeypatch.setattr(guided.Prompt, "ask", fake_prompt)
    options = guided._prompt_guided_options(console, default_max=5, run_id="run-1")
    assert options.max_flights == 2
    assert options.force is True
    assert options.start_date == "2026-01-01"
    assert options.end_date is None


def test_guided_filter_summaries_by_date():
    summaries = [
        FlightSummary("A1", None, None, None, None),
        FlightSummary("A2", datetime(2026, 1, 2, tzinfo=timezone.utc), None, None, None),
    ]
    filtered = guided._filter_summaries_by_date(
        summaries,
        datetime(2026, 1, 2, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    assert [summary.id for summary in filtered] == ["A2"]


def test_preflight_checks_failure_paths():
    console = Console(file=io.StringIO())

    class BadCloudAhoy:
        def list_flights(self, limit=None):
            raise RuntimeError("boom")

    class BadFlySto:
        def prepare(self):
            return False

    assert guided._preflight_checks(console, BadCloudAhoy(), BadFlySto()) is False


def test_progress_callback_start_end():
    console = Console(file=io.StringIO())
    progress = guided._build_progress(console, total=1)
    task_id = progress.add_task("Uploading", total=1)
    handler = guided._progress_callback(progress, task_id, console)
    handler("start", {"flight_id": "F1"})
    handler("end", {"flight_id": "F1", "status": "ok"})


def test_parse_date_bound_with_time():
    dt = guided._parse_date_bound("2026-01-02T01:02:03Z", is_end=False)
    assert dt.tzinfo is not None
