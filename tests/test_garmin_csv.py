from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.cloudahoy.points import write_points_garmin_g1000_csv, write_points_garmin_g3x_csv


def _schema() -> list[dict]:
    return [
        {"index": 0, "name": "longitude_deg"},
        {"index": 1, "name": "latitude_deg"},
        {"index": 2, "name": "alt_meters"},
        {"index": 3, "name": "gs_knots"},
        {"index": 4, "name": "tas_knots"},
        {"index": 5, "name": "crs_degrees"},
        {"index": 6, "name": "heading_deg"},
        {"index": 7, "name": "ias_knots"},
        {"index": 8, "name": "vs_fpm"},
        {"index": 9, "name": "roll_deg"},
        {"index": 10, "name": "pitch_deg"},
        {"index": 11, "name": "alt_meters_raw"},
    ]


def _point_row() -> list:
    row = [None] * 12
    row[0] = 14.0
    row[1] = 48.0
    row[2] = 1000.0
    row[3] = 90.0
    row[4] = 95.0
    row[5] = 180.0
    row[6] = 175.0
    row[7] = 80.0
    row[8] = 500.0
    row[9] = 10.0
    row[10] = 5.0
    row[11] = 1100.0
    return row


def test_garmin_g3x_csv_header_and_row(tmp_path: Path) -> None:
    out_path = tmp_path / "g3x.csv"
    start = datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc)
    metadata = {"tail_number": "D-KBUH", "aircraft_type": "WT9"}
    write_points_garmin_g3x_csv(
        [_point_row()],
        _schema(),
        out_path,
        start_time=start,
        step_seconds=1.0,
        metadata=metadata,
    )

    with out_path.open() as handle:
        rows = list(csv.reader(handle))

    assert rows[0][0].startswith("#airframe_info")
    units = rows[1]
    assert "UTC Offset (hh:mm)" in units
    header = rows[2]
    assert header[:3] == ["Lcl Date", "Lcl Time", "UTCOfst"]
    data = rows[3]
    assert data[0] == "2024-09-04"
    assert data[1] == "12:00:00"
    assert data[2] == "+00:00"
    assert float(data[3]) == 48.0
    assert float(data[4]) == 14.0


def test_garmin_g1000_csv_header_and_row(tmp_path: Path) -> None:
    out_path = tmp_path / "g1000.csv"
    start = datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc)
    metadata = {"tail_number": "D-KBUH", "aircraft_type": "WT9"}
    write_points_garmin_g1000_csv(
        [_point_row()],
        _schema(),
        out_path,
        start_time=start,
        step_seconds=1.0,
        metadata=metadata,
    )

    with out_path.open() as handle:
        rows = list(csv.reader(handle))

    assert rows[0][0].startswith("#airframe_info")
    units = rows[1]
    assert "UTC Offset (hh:mm)" in units
    header = rows[2]
    assert header[:3] == ["Lcl Date", "Lcl Time", "UTCOfst"]
    data = rows[3]
    assert data[0] == "09/04/2024"
    assert data[1] == "12:00:00"
    assert data[2] == "+00:00"
    assert float(data[3]) == 48.0
    assert float(data[4]) == 14.0
