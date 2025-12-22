from __future__ import annotations

import csv
from datetime import datetime, timezone, timedelta
import re
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element, SubElement, ElementTree


INFERRED_COLUMNS: dict[int, dict[str, Any]] = {
    6: {"name": "heading_deg", "unit": "deg", "label": "heading/track", "confidence": "high"},
    7: {"name": "wind_speed_knots", "unit": "knots", "label": "wind speed", "confidence": "medium"},
    8: {"name": "wind_dir_deg", "unit": "deg", "label": "wind direction", "confidence": "medium"},
    11: {"name": "mag_variation_deg", "unit": "deg", "label": "mag variation", "confidence": "high"},
    12: {"name": "vs_knots", "unit": "knots", "label": "vertical speed", "confidence": "medium"},
    13: {"name": "roll_deg", "unit": "deg", "label": "roll/bank", "confidence": "medium"},
    14: {"name": "airborne_flag", "unit": None, "label": "airborne flag", "confidence": "high"},
    15: {"name": "valid_flag", "unit": None, "label": "valid flag", "confidence": "low"},
    16: {"name": "ias_knots", "unit": "knots", "label": "indicated airspeed", "confidence": "high"},
    18: {"name": "alt_meters_raw", "unit": "meters", "label": "altitude (raw)", "confidence": "low"},
    19: {"name": "agl_meters", "unit": "meters", "label": "altitude AGL", "confidence": "high"},
    20: {"name": "alt_meters_smooth", "unit": "meters", "label": "altitude (smooth)", "confidence": "low"},
}


def build_points_schema(flt: dict) -> list[dict[str, Any]]:
    points = flt.get("points") if isinstance(flt, dict) else None
    if not isinstance(points, list) or not points:
        return []
    max_len = max(len(point) for point in points if isinstance(point, list))
    if max_len == 0:
        return []

    schema = []
    for idx in range(max_len):
        schema.append(
            {
                "index": idx,
                "name": f"col_{idx}",
                "unit": None,
                "label": None,
                "id": None,
                "source": "unknown",
                "confidence": None,
            }
        )

    mapping = _extract_profiles(flt.get("p"))
    for idx, meta in mapping.items():
        if idx < len(schema):
            schema[idx] = {
                "index": idx,
                "name": meta["name"],
                "unit": meta["unit"],
                "label": meta["label"],
                "id": meta["id"],
                "source": "profile",
                "confidence": "high",
            }

    if 0 < len(schema):
        schema[0] = {
            "index": 0,
            "name": "longitude_deg",
            "unit": "deg",
            "label": "longitude",
            "id": "LON",
            "source": "inferred",
            "confidence": "high",
        }
    if 1 < len(schema):
        schema[1] = {
            "index": 1,
            "name": "latitude_deg",
            "unit": "deg",
            "label": "latitude",
            "id": "LAT",
            "source": "inferred",
            "confidence": "high",
        }

    for idx, meta in INFERRED_COLUMNS.items():
        if idx < len(schema) and schema[idx]["source"] == "unknown":
            schema[idx] = {
                "index": idx,
                "name": meta["name"],
                "unit": meta["unit"],
                "label": meta["label"],
                "id": None,
                "source": "inferred",
                "confidence": meta.get("confidence"),
            }

    return schema


def write_points_csv(points: list, schema: list[dict[str, Any]], path: Path) -> None:
    header = [column["name"] for column in schema]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        for point in points:
            if not isinstance(point, list):
                continue
            row = [point[idx] if idx < len(point) else None for idx in range(len(schema))]
            writer.writerow(row)

def infer_point_indices(schema: list[dict[str, Any]]) -> tuple[int, int, int | None]:
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)
    return lat_idx, lon_idx, alt_idx


def write_points_gpx(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | float | int | None = None,
    step_seconds: float | None = None,
    track_name: str | None = None,
) -> None:
    lat_idx, lon_idx, alt_idx = infer_point_indices(schema)
    if start_time is not None:
        if isinstance(start_time, (int, float)):
            start_time = datetime.fromtimestamp(float(start_time), tz=timezone.utc)
        elif isinstance(start_time, datetime):
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
        else:
            start_time = None
    if step_seconds is None or step_seconds <= 0:
        step_seconds = 1.0

    gpx = Element("gpx", {
        "version": "1.1",
        "creator": "skybridge",
        "xmlns": "http://www.topografix.com/GPX/1/1",
    })
    trk = SubElement(gpx, "trk")
    if track_name:
        name = SubElement(trk, "name")
        name.text = track_name
    trkseg = SubElement(trk, "trkseg")

    for idx, point in enumerate(points):
        if not isinstance(point, list):
            continue
        if lon_idx >= len(point) or lat_idx >= len(point):
            continue
        lon = point[lon_idx]
        lat = point[lat_idx]
        if lon is None or lat is None:
            continue
        trkpt = SubElement(trkseg, "trkpt", {
            "lat": str(lat),
            "lon": str(lon),
        })
        if alt_idx is not None and alt_idx < len(point):
            alt = point[alt_idx]
            if alt is not None:
                ele = SubElement(trkpt, "ele")
                ele.text = str(alt)
        if start_time is not None:
            timestamp = start_time + timedelta(seconds=step_seconds * idx)
            time_node = SubElement(trkpt, "time")
            time_node.text = timestamp.isoformat().replace("+00:00", "Z")

    path.parent.mkdir(parents=True, exist_ok=True)
    tree = ElementTree(gpx)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _index_for(schema: list[dict[str, Any]], name: str, fallback: int | None = None) -> int | None:
    for column in schema:
        if column.get("name") == name:
            return int(column.get("index", fallback or 0))
    return fallback



def points_preview(
    points: list, schema: list[dict[str, Any]], limit: int = 3
) -> list[dict[str, Any]]:
    preview: list[dict[str, Any]] = []
    header = [column["name"] for column in schema]
    for point in points[:limit]:
        if not isinstance(point, list):
            continue
        row = {}
        for idx, name in enumerate(header):
            row[name] = point[idx] if idx < len(point) else None
        preview.append(row)
    return preview


def _extract_profiles(profiles: Any) -> dict[int, dict[str, Any]]:
    mapping: dict[int, dict[str, Any]] = {}
    if not isinstance(profiles, list):
        return mapping
    used_names: set[str] = set()
    for item in profiles:
        if not isinstance(item, dict):
            continue
        label = item.get("label")
        p_id = item.get("id")
        for profile in item.get("profiles", []) or []:
            if not isinstance(profile, dict):
                continue
            pindex = profile.get("pindex")
            if pindex is None:
                continue
            unit = profile.get("unit")
            name = _slug(p_id or label or f"p{pindex}")
            if unit:
                name = f"{name}_{_slug(unit)}"
            if name in used_names:
                name = f"{name}_{pindex}"
            used_names.add(name)
            mapping[int(pindex)] = {
                "name": name,
                "unit": unit,
                "label": label,
                "id": p_id,
            }
    return mapping


def _slug(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_") or "col"
