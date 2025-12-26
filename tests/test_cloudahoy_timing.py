from __future__ import annotations

from datetime import datetime, timezone

from src.cloudahoy.client import _infer_point_timing


def test_infer_point_timing_prefers_summary_air_window() -> None:
    flt = {
        "Meta": {
            "GMT_start": 1_000_000,
            "air": 0.5,
            "gnd": 0.5,
            "summary": {
                "air": {
                    "start": 1_000_100,
                    "end": 1_000_106,
                }
            },
        }
    }
    start_time, step = _infer_point_timing(flt, points_count=4)
    assert start_time == datetime.fromtimestamp(1_000_100, tz=timezone.utc)
    assert step == 2.0
