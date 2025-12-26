from __future__ import annotations

from datetime import datetime, timezone

from src.cli import _filter_summaries_by_date, _parse_date_bound
from src.models import FlightSummary


def test_parse_date_bound_date_start_and_end():
    start = _parse_date_bound("2024-09-04", is_end=False)
    end = _parse_date_bound("2024-09-04", is_end=True)
    assert start == datetime(2024, 9, 4, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2024, 9, 4, 23, 59, 59, 999999, tzinfo=timezone.utc)


def test_filter_summaries_by_date_inclusive():
    summaries = [
        FlightSummary("a", datetime(2024, 9, 3, 12, 0, tzinfo=timezone.utc), None, None, None),
        FlightSummary("b", datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc), None, None, None),
        FlightSummary("c", datetime(2024, 9, 5, 12, 0, tzinfo=timezone.utc), None, None, None),
    ]
    start = _parse_date_bound("2024-09-04", is_end=False)
    end = _parse_date_bound("2024-09-04", is_end=True)
    filtered = _filter_summaries_by_date(summaries, start, end)
    assert [s.id for s in filtered] == ["b"]
