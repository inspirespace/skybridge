"""Shared date/time helpers used across core and backend."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable, TypeVar

_SummaryT = TypeVar("_SummaryT")


def format_iso_z(value: datetime) -> str:
    """Format a datetime as ISO-8601 with a trailing ``Z`` for UTC."""
    return value.isoformat().replace("+00:00", "Z")


def now_iso_z() -> str:
    """Return the current UTC time as an ISO-8601 ``Z`` string."""
    return format_iso_z(datetime.now(timezone.utc))


def parse_iso_z(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, tolerating a trailing ``Z``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def parse_date_bound(value: str, is_end: bool) -> datetime:
    """Parse a CLI-style date bound (``YYYY-MM-DD`` or full ISO) into a UTC datetime."""
    raw = value.strip()
    normalized = raw.replace("Z", "+00:00")
    if "T" not in normalized and len(normalized) == 10:
        dt = datetime.fromisoformat(normalized)
        if is_end:
            dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
        else:
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def filter_summaries_by_date(
    summaries: Iterable[_SummaryT],
    start_date: datetime | None,
    end_date: datetime | None,
) -> list[_SummaryT]:
    """Filter flight summaries whose ``started_at`` falls within the given bounds."""
    if not start_date and not end_date:
        return list(summaries)
    filtered: list[_SummaryT] = []
    for summary in summaries:
        started_at = getattr(summary, "started_at", None)
        if started_at is None:
            continue
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        if start_date and started_at < start_date:
            continue
        if end_date and started_at > end_date:
            continue
        filtered.append(summary)
    return filtered
