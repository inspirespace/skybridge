from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


def build_points_schema(flt: dict) -> list[dict[str, Any]]:
    points = flt.get("points") if isinstance(flt, dict) else None
    if not isinstance(points, list) or not points:
        return []
    max_len = max(len(point) for point in points if isinstance(point, list))
    if max_len == 0:
        return []

    schema = [
        {"index": idx, "name": f"col_{idx}", "unit": None, "label": None, "id": None}
        for idx in range(max_len)
    ]

    mapping = _extract_profiles(flt.get("p"))
    for idx, meta in mapping.items():
        if idx < len(schema):
            schema[idx] = {
                "index": idx,
                "name": meta["name"],
                "unit": meta["unit"],
                "label": meta["label"],
                "id": meta["id"],
            }

    if 0 < len(schema):
        schema[0] = {
            "index": 0,
            "name": "longitude_deg",
            "unit": "deg",
            "label": "longitude",
            "id": "LON",
        }
    if 1 < len(schema):
        schema[1] = {
            "index": 1,
            "name": "latitude_deg",
            "unit": "deg",
            "label": "latitude",
            "id": "LAT",
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
