"""tests/test_mvp50_csv.py module."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.core.cloudahoy.points import write_points_mvp50_csv


def _schema() -> list[dict]:
    """Internal helper for schema."""
    return [
        {"index": 0, "name": "longitude_deg"},
        {"index": 1, "name": "latitude_deg"},
        {"index": 2, "name": "alt_meters"},
        {"index": 3, "name": "gs_knots"},
    ]


def _point_row() -> list:
    """Internal helper for point row."""
    row = [None] * 4
    row[0] = 14.0
    row[1] = 48.0
    row[2] = 1000.0
    row[3] = 90.0
    return row


def test_mvp50_csv_header_and_row(tmp_path: Path) -> None:
    """Test mvp50 csv header and row."""
    out_path = tmp_path / "flight.csv"
    start = datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc)
    write_points_mvp50_csv(
        [_point_row()],
        _schema(),
        out_path,
        start_time=start,
        step_seconds=1.0,
        metadata={},
    )

    with out_path.open() as handle:
        rows = list(csv.reader(handle))

    header_idx = next(i for i, row in enumerate(rows) if row and row[0] == "TIME")
    header = rows[header_idx]
    assert header[-5:] == ["GPS-WAYPT", "GPS-LAT", "GPS-LONG", "GPSSPEED;KTS", "GPS-ALT;F"]

    data = rows[header_idx + 1]
    assert data[0] == "12:00:00"
    assert float(data[34]) == 48.0
    assert float(data[35]) == 14.0
    assert float(data[36]) == 90.0
    assert float(data[37]) == 3280.84
