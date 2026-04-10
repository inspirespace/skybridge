"""Extra tests for backend service helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import src.backend.service as service
from src.core.models import FlightSummary


def test_parse_export_formats_and_short_id():
    assert service._parse_export_formats("g3x,gpx") == ["g3x", "gpx"]
    assert service._parse_export_formats("cloudahoy") == ["gpx"]
    assert service._short_flight_id("ABC") == "ABC"
    assert service._short_flight_id("123456789012345") == "...89012345"


def test_summaries_from_review_parses_dates():
    payload = {
        "items": [
            {"flight_id": "F1", "started_at": "2026-01-01T10:00:00Z"},
            {"flight_id": "", "started_at": "2026-01-01T10:00:00Z"},
        ]
    }
    summaries = service._summaries_from_review(payload)
    assert len(summaries) == 1
    assert summaries[0].id == "F1"
    assert summaries[0].started_at is not None


def test_summaries_for_range_filters():
    summaries = [
        FlightSummary("A1", datetime(2026, 1, 1, tzinfo=timezone.utc), None, None, None),
        FlightSummary("A2", datetime(2026, 1, 2, tzinfo=timezone.utc), None, None, None),
    ]

    class DummyCloudAhoy:
        def list_flights(self, limit=None):
            return summaries

    filtered = service._summaries_for_range(
        DummyCloudAhoy(), "2026-01-02", "2026-01-02", max_flights=None
    )
    assert [item.id for item in filtered] == ["A2"]


def test_summaries_for_range_applies_max_after_date_filtering():
    summaries = [
        FlightSummary("A1", datetime(2026, 1, 5, tzinfo=timezone.utc), None, None, None),
        FlightSummary("A2", datetime(2026, 1, 4, tzinfo=timezone.utc), None, None, None),
        FlightSummary("A3", datetime(2026, 1, 3, tzinfo=timezone.utc), None, None, None),
    ]
    seen_limits: list[int | None] = []

    class DummyCloudAhoy:
        def list_flights(self, limit=None):
            seen_limits.append(limit)
            if limit is None:
                return summaries
            return summaries[:limit]

    filtered = service._summaries_for_range(
        DummyCloudAhoy(), "2026-01-03", "2026-01-04", max_flights=1
    )

    assert seen_limits == [None]
    assert [item.id for item in filtered] == ["A2"]


def test_build_review_summary_and_locations():
    items = [
        SimpleNamespace(
            flight_id="F1",
            started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            duration_seconds=3600,
            tail_number=None,
            metadata={"origin": {"c": "KSEA"}, "destination": "KLAX"},
            status="ok",
            message=None,
        )
    ]
    summary = service._build_review_summary(items)
    assert summary.flight_count == 1
    assert summary.missing_tail_numbers == 1
    assert summary.flights[0].origin == "KSEA"
    assert summary.flights[0].destination == "KLAX"


def test_maybe_wait_for_processing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("BACKEND_WAIT_FOR_PROCESSING", "1")
    monkeypatch.setenv("BACKEND_PROCESSING_INTERVAL", "0")
    monkeypatch.setenv("BACKEND_PROCESSING_TIMEOUT", "0.01")

    class DummyFlySto:
        def __init__(self):
            self.calls = 0

        def log_files_to_process(self):
            self.calls += 1
            return 1 if self.calls < 3 else 0

    service._maybe_wait_for_processing(DummyFlySto())


def test_env_helpers_and_base_urls(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEV_USE_MOCKS", "1")
    monkeypatch.setenv("MOCK_CLOUD_AHOY_BASE_URL", "http://mock-cloudahoy")
    monkeypatch.setenv("MOCK_FLYSTO_BASE_URL", "http://mock-flysto")
    assert service._cloudahoy_base_url() == "http://mock-cloudahoy"
    assert service._flysto_base_url() == "http://mock-flysto"

    monkeypatch.setenv("FLOAT_VAL", "bad")
    assert service._float_env("FLOAT_VAL", 1.5) == 1.5
    monkeypatch.setenv("INT_VAL", "bad")
    assert service._int_env("INT_VAL", 3) == 3
