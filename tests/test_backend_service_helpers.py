"""Tests for backend service helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from src.backend import service
from src.backend.models import JobRecord, ProgressEvent
from src.core.models import FlightSummary as CoreFlightSummary


@dataclass
class FakeReviewItem:
    flight_id: str
    started_at: datetime | None
    duration_seconds: int | None
    tail_number: str | None
    metadata: dict | None
    status: str | None
    message: str | None


def test_parse_date_bound_date_only_start_end() -> None:
    """Test date-only bounds normalize to day start/end in UTC."""
    start = service._parse_date_bound("2026-01-05", is_end=False)
    end = service._parse_date_bound("2026-01-05", is_end=True)

    assert start == datetime(2026, 1, 5, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 5, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_parse_date_bound_handles_iso_z() -> None:
    """Test ISO timestamp with Z is parsed with UTC tzinfo."""
    parsed = service._parse_date_bound("2026-01-05T10:30:00Z", is_end=False)
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 10
    assert parsed.minute == 30


def test_filter_summaries_by_date_handles_naive_and_aware() -> None:
    """Test filtering respects boundaries and normalizes naive timestamps."""
    summaries = [
        CoreFlightSummary(
            id="a",
            started_at=datetime(2026, 1, 4, 23, 0, tzinfo=timezone.utc),
            duration_seconds=None,
            aircraft_type=None,
            tail_number=None,
        ),
        CoreFlightSummary(
            id="b",
            started_at=datetime(2026, 1, 5, 0, 0),
            duration_seconds=None,
            aircraft_type=None,
            tail_number=None,
        ),
        CoreFlightSummary(
            id="c",
            started_at=datetime(2026, 1, 7, 23, 59, tzinfo=timezone.utc),
            duration_seconds=None,
            aircraft_type=None,
            tail_number=None,
        ),
        CoreFlightSummary(
            id="d",
            started_at=datetime(2026, 1, 8, 0, 0, tzinfo=timezone.utc),
            duration_seconds=None,
            aircraft_type=None,
            tail_number=None,
        ),
    ]

    start = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)
    end = datetime(2026, 1, 7, 23, 59, tzinfo=timezone.utc)

    filtered = service._filter_summaries_by_date(summaries, start, end)
    assert [summary.id for summary in filtered] == ["b", "c"]


def test_parse_export_formats_dedupes_and_appends_gpx() -> None:
    """Test export format parsing handles aliases and duplicates."""
    assert service._parse_export_formats(None) == ["g3x", "gpx"]
    parsed = service._parse_export_formats("g3x; cloudahoy; gpx; G3X")
    assert parsed == ["g3x", "gpx"]


def test_summaries_from_review_filters_invalid_entries() -> None:
    """Test review payload parsing ignores invalid items and parses dates."""
    payload = {
        "items": [
            {
                "flight_id": "flight-1",
                "started_at": "2026-01-05T12:00:00Z",
                "duration_seconds": 3600,
                "aircraft_type": "C172",
                "tail_number": "N123",
            },
            {"flight_id": ""},
            "bad-entry",
        ]
    }

    summaries = service._summaries_from_review(payload)
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.id == "flight-1"
    assert summary.started_at == datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    assert summary.duration_seconds == 3600


def test_build_review_summary_collects_metrics_and_locations() -> None:
    """Test review summary aggregates hours, dates, and locations."""
    items = [
        FakeReviewItem(
            flight_id="flight-1",
            started_at=datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            tail_number=None,
            metadata={"origin": {"c": "KSEA"}, "destination": {"t": "KLAX"}},
            status="ok",
            message=None,
        ),
        FakeReviewItem(
            flight_id="flight-2",
            started_at=datetime(2026, 1, 6, 9, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
            tail_number="N456",
            metadata={"origin": "KSFO", "destination": "KPDX"},
            status="ok",
            message=None,
        ),
    ]

    summary = service._build_review_summary(items)
    assert summary.flight_count == 2
    assert summary.total_hours == 1.5
    assert summary.missing_tail_numbers == 1
    assert summary.earliest_date == datetime(2026, 1, 5, 9, 0, tzinfo=timezone.utc).isoformat()
    assert summary.latest_date == datetime(2026, 1, 6, 9, 0, tzinfo=timezone.utc).isoformat()
    assert summary.flights[0].origin == "KSEA"
    assert summary.flights[0].destination == "KLAX"
    assert summary.flights[0].flight_time_minutes == 60


def test_append_progress_trims_log_and_updates_job() -> None:
    """Test progress events append and trim at 200 entries."""
    now = datetime(2026, 1, 5, 10, 0, tzinfo=timezone.utc)
    events = [
        ProgressEvent(
            phase="review",
            stage=f"stage-{idx}",
            flight_id=None,
            percent=idx,
            status="review_running",
            created_at=now,
        )
        for idx in range(200)
    ]

    job = JobRecord(
        job_id=uuid4(),
        user_id="pilot",
        status="review_running",
        created_at=now,
        updated_at=now,
        progress_log=events,
    )

    service._append_progress(
        job,
        phase="review",
        stage="stage-final",
        percent=100,
        status="review_ready",
    )

    assert len(job.progress_log) == 200
    assert all(event.stage != "stage-0" for event in job.progress_log)
    assert job.progress_log[-1].stage == "stage-final"
    assert job.progress_stage == "stage-final"
    assert job.progress_percent == 100


@pytest.mark.parametrize(
    "value,expected",
    [
        ("short", "short"),
        ("123456789012", "123456789012"),
        ("flight-id-0000000000", "...00000000"),
    ],
)
def test_short_flight_id(value: str, expected: str) -> None:
    """Test flight id shortening keeps short values intact."""
    assert service._short_flight_id(value) == expected


def test_background_heartbeat_ticks_while_main_thread_blocks() -> None:
    """Background heartbeat must fire while the main thread is stuck."""
    import time

    ticks: list[float] = []

    def beat() -> None:
        ticks.append(time.monotonic())

    # 0.05s interval so the test runs fast; the real default is 30s.
    with service._BackgroundHeartbeat(beat, interval_seconds=0.05):
        time.sleep(0.25)

    # Expect at least 2 ticks within 0.25s at 0.05s interval; allow slack for
    # CI scheduling jitter.
    assert len(ticks) >= 2


def test_background_heartbeat_is_noop_when_callable_is_none() -> None:
    """Passing None must not spawn a thread."""
    with service._BackgroundHeartbeat(None, interval_seconds=0.01) as bh:
        assert bh._thread is None


def test_background_heartbeat_swallows_exceptions() -> None:
    """A failing heartbeat must not crash the worker."""
    import time

    call_count = {"n": 0}

    def flaky() -> None:
        call_count["n"] += 1
        raise RuntimeError("firestore unavailable")

    with service._BackgroundHeartbeat(flaky, interval_seconds=0.02):
        time.sleep(0.1)

    assert call_count["n"] >= 2
