"""tests/test_foreflight_csv.py module."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from src.core.cloudahoy.points import write_points_foreflight_csv


def _schema() -> list[dict]:
    """Internal helper for schema."""
    return [
        {"index": 0, "name": "longitude_deg"},
        {"index": 1, "name": "latitude_deg"},
        {"index": 2, "name": "alt_meters"},
        {"index": 3, "name": "gs_knots"},
        {"index": 4, "name": "tas_knots"},
        {"index": 5, "name": "crs_degrees"},
        {"index": 6, "name": "heading_deg"},
        {"index": 7, "name": "wind_speed_knots"},
        {"index": 8, "name": "wind_dir_deg"},
        {"index": 9, "name": "vs_fpm"},
        {"index": 11, "name": "mag_variation_deg"},
        {"index": 14, "name": "pitch_deg"},
        {"index": 13, "name": "roll_deg"},
        {"index": 18, "name": "alt_meters_raw"},
        {"index": 19, "name": "agl_meters"},
        {"index": 20, "name": "alt_meters_smooth"},
    ]


def _point_row() -> list:
    """Internal helper for point row."""
    row = [None] * 21
    row[0] = 14.0
    row[1] = 48.0
    row[2] = 1000.0
    row[3] = 90.0
    row[4] = 95.0
    row[5] = 180.0
    row[6] = 175.0
    row[7] = 12.0
    row[8] = 90.0
    row[9] = 500.0
    row[11] = 2.5
    row[14] = 5.0
    row[13] = 10.0
    row[18] = 1100.0
    row[19] = 400.0
    row[20] = 1050.0
    return row


def test_foreflight_csv_header_and_row(tmp_path: Path) -> None:
    """Test foreflight csv header and row."""
    out_path = tmp_path / "flight.csv"
    start = datetime(2024, 9, 4, 12, 0, tzinfo=timezone.utc)
    metadata = {"tail_number": "D-KBUH", "pilot": ["Ulrich", "u@example.com"]}
    write_points_foreflight_csv(
        [_point_row()],
        _schema(),
        out_path,
        start_time=start,
        step_seconds=1.0,
        metadata=metadata,
    )

    with out_path.open() as handle:
        rows = list(csv.reader(handle))

    data_index = next(i for i, row in enumerate(rows) if row and row[0] == "DATA")
    meta_rows = {row[0]: row[1] for row in rows[:data_index] if row}
    assert meta_rows.get("METADATA") == "CA_CSV.3"
    assert meta_rows.get("TAIL") == "D-KBUH"
    assert meta_rows.get("PILOT") == "Ulrich"

    header = rows[data_index + 1]
    assert "seconds/t" in header
    assert "degrees/lat" in header
    assert "degrees/lon" in header
    assert "feet/Alt (gps)" in header
    assert "knots/GS" in header
    assert "knots/TAS" in header
    assert "degrees/TRK" in header
    assert "degrees/HDG" in header
    assert "fpm/VS" in header
    assert "degrees/ROLL" in header
    assert "degrees/Pitch" in header
    assert "degrees/MagVar" in header
    assert "knots/WndSpd" in header
    assert "degrees/WndDr" in header
    assert "feet/AGL" in header
    assert "ft msl/AltMSL" in header
    assert "ft baro/AltB" in header

    data = rows[data_index + 2]
    idx = {name: i for i, name in enumerate(header)}
    assert float(data[idx["seconds/t"]]) == 0.0
    assert float(data[idx["feet/Alt (gps)"]]) == 3280.84
    assert float(data[idx["ft msl/AltMSL"]]) == 3608.924
    assert float(data[idx["ft baro/AltB"]]) == 3444.882
