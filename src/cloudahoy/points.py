from __future__ import annotations

import csv
import math
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


def write_points_foreflight_csv(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | None,
    step_seconds: float | None,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_index = {column["name"]: column["index"] for column in schema}
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)

    gmt_epoch = _infer_gmt_epoch(start_time, metadata)
    step = step_seconds if step_seconds and step_seconds > 0 else 1.0
    stride = 1
    if step > 0 and step < 0.25:
        stride = max(1, int(math.ceil(0.25 / step)))

    columns = _foreflight_columns(schema_index, alt_idx)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        for key, value in _foreflight_metadata(metadata, gmt_epoch):
            writer.writerow([key, value])
        writer.writerow(["DATA", ""])
        writer.writerow([col[0] for col in columns])

        for idx, point in enumerate(points):
            if idx % stride != 0:
                continue
            if not isinstance(point, list):
                continue
            row = []
            for header, provider in columns:
                row.append(provider(point, idx, step))
            writer.writerow(row)


def write_points_flightradar24_csv(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | None,
    step_seconds: float | None,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_index = {column["name"]: column["index"] for column in schema}
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)
    trk_idx = schema_index.get("crs_degrees") or schema_index.get("heading_deg")
    gs_idx = schema_index.get("gs_knots")

    gmt_epoch = _infer_gmt_epoch(start_time, metadata)
    step = step_seconds if step_seconds and step_seconds > 0 else 1.0
    stride = 1
    if step > 0 and step < 0.25:
        stride = max(1, int(math.ceil(0.25 / step)))

    callsign = metadata.get("callsign") or metadata.get("tail_number") or ""

    def meters_to_feet(value: Any):
        return float(value) * 3.28084

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["timestamp", "callsign", "latitude", "longitude", "altitude", "speed", "heading"]
        )
        for idx, point in enumerate(points):
            if idx % stride != 0:
                continue
            if not isinstance(point, list):
                continue
            timestamp = int(gmt_epoch + (idx * step))
            lat = point[lat_idx] if lat_idx is not None and lat_idx < len(point) else ""
            lon = point[lon_idx] if lon_idx is not None and lon_idx < len(point) else ""
            alt = (
                meters_to_feet(point[alt_idx])
                if alt_idx is not None and alt_idx < len(point) and point[alt_idx] is not None
                else ""
            )
            speed = point[gs_idx] if gs_idx is not None and gs_idx < len(point) else ""
            heading = point[trk_idx] if trk_idx is not None and trk_idx < len(point) else ""
            writer.writerow([timestamp, callsign, lat, lon, alt, speed, heading])


def write_points_mvp50_csv(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | None,
    step_seconds: float | None,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_index = {column["name"]: column["index"] for column in schema}
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)
    gs_idx = schema_index.get("gs_knots")

    gmt_epoch = _infer_gmt_epoch(start_time, metadata)
    base_time = datetime.fromtimestamp(gmt_epoch, tz=timezone.utc)
    step = step_seconds if step_seconds and step_seconds > 0 else 1.0
    stride = 1
    if step > 0 and step < 0.25:
        stride = max(1, int(math.ceil(0.25 / step)))

    def meters_to_feet(value: Any):
        return float(value) * 3.28084

    def fmt_time(ts: datetime) -> str:
        return ts.strftime("%H:%M:%S")

    def fmt_date(ts: datetime) -> str:
        return ts.strftime("%m/%d/%y")

    header_fields = [
        "TIME",
        "MSTR_WRN",
        "RPM;RPM",
        "F.FLOW;G/HR",
        "FUEL L;GAL",
        "FUEL R;GAL",
        "F.AUX;GAL",
        "VOLTS;V",
        "AMPS;A",
        "M.P.;\"HG",
        "OIL P.;PSI",
        "VAC;\"HG",
        "FUEL P;PSI",
        "HYD P.;PSI",
        "WATR P;PSI",
        "OAT;*F",
        "TIT;*F",
        "EGT 1;*F",
        "EGT 4;*F",
        "EGT 3;*F",
        "EGT 2;*F",
        "EGT 5;*F",
        "EGT 6;*F",
        "CHT 1;*F",
        "CHT 2;*F",
        "CHT 3;*F",
        "CHT 4;*F",
        "CHT 5;*F",
        "CHT 6;*F",
        "OIL T.;*F",
        "FLAPS;DEG",
        "HP;%",
        "S.COOL;*F/M",
        "GPS-WAYPT",
        "GPS-LAT",
        "GPS-LONG",
        "GPSSPEED;KTS",
        "GPS-ALT;F",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        handle.write("Electronics International Inc.\n")
        handle.write("MVP-50 Flight Data Recording\n")
        handle.write("Hardware ID: 0\n")
        handle.write("Software ID: 0\n")
        handle.write("Unit ID: 0\n")
        handle.write("Engine Data Converter Model: EDC\n")
        handle.write("Flight Number: 1\n")
        handle.write(f"Local Time: {fmt_date(base_time)} {fmt_time(base_time)}\n")
        handle.write("Date Format: mm/dd/yy\n")
        handle.write(f"ZULU Time: {fmt_time(base_time)}\n")
        handle.write("Engine Hours: 0.00 Hours\n")
        handle.write("Tach Time: 0.00 Hours\n")
        handle.write(f"Data Logging Interval: {int(round(step))} sec\n")
        writer = csv.writer(handle)
        writer.writerow(header_fields)

        for idx, point in enumerate(points):
            if idx % stride != 0:
                continue
            if not isinstance(point, list):
                continue
            row_time = base_time + timedelta(seconds=idx * step)
            lat = point[lat_idx] if lat_idx is not None and lat_idx < len(point) else ""
            lon = point[lon_idx] if lon_idx is not None and lon_idx < len(point) else ""
            alt = (
                meters_to_feet(point[alt_idx])
                if alt_idx is not None and alt_idx < len(point) and point[alt_idx] is not None
                else ""
            )
            speed = point[gs_idx] if gs_idx is not None and gs_idx < len(point) else ""

            row = [""] * len(header_fields)
            row[0] = fmt_time(row_time)
            row[34] = lat
            row[35] = lon
            row[36] = speed
            row[37] = alt
            writer.writerow(row)


def write_points_garmin_g3x_csv(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | None,
    step_seconds: float | None,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_index = {column["name"]: column["index"] for column in schema}
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)
    alt_raw_idx = schema_index.get("alt_meters_raw")
    tas_idx = schema_index.get("tas_knots")
    ias_idx = schema_index.get("ias_knots")
    gs_idx = schema_index.get("gs_knots")
    trk_idx = schema_index.get("crs_degrees")
    hdg_idx = schema_index.get("heading_deg")
    vs_idx = schema_index.get("vs_fpm")
    vs_knots_idx = schema_index.get("vs_knots")
    roll_idx = schema_index.get("roll_deg")
    pitch_idx = schema_index.get("pitch_deg")
    oat_idx = schema_index.get("oat_c")

    gmt_epoch = _infer_gmt_epoch(start_time, metadata)
    base_time = datetime.fromtimestamp(gmt_epoch, tz=timezone.utc)
    step = step_seconds if step_seconds and step_seconds > 0 else 1.0
    stride = 1
    if step > 0 and step < 0.25:
        stride = max(1, int(math.ceil(0.25 / step)))

    def meters_to_feet(value: Any):
        return float(value) * 3.28084

    def knots_to_fpm(value: Any):
        return float(value) * 101.2686

    def fmt_date(ts: datetime) -> str:
        return ts.strftime("%Y-%m-%d")

    def fmt_time(ts: datetime) -> str:
        return ts.strftime("%H:%M:%S")

    airframe = metadata.get("aircraft_type") or "Unknown"
    tail = metadata.get("tail_number") or ""

    header_lines = [
        f"#airframe_info,1,{airframe},G3X,{tail}",
        "Lcl Date (yyyy-mm-dd),Lcl Time (hh:mm:ss),UTC Offset (hh:mm),Latitude (deg),Longitude (deg),"
        "GPS Alt (ft),Pressure Alt (ft),IAS (kt),TAS (kt),GS (kt),Heading (deg),Pitch (deg),Roll (deg),"
        "VS (ft/min),OAT (C),Fuel Flow (GPH),RPM,Manifold Pressure (inHg),CHT1 (F),EGT1 (F)",
        "Lcl Date,Lcl Time,UTCOfst,Latitude,Longitude,AltGPS,AltB,IAS,TAS,GndSpd,HDG,Pitch,Roll,VSpd,OAT,"
        "FF,RPM,ManP,CHT1,EGT1",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        for line in header_lines:
            handle.write(f"{line}\n")
        writer = csv.writer(handle)
        for idx, point in enumerate(points):
            if idx % stride != 0:
                continue
            if not isinstance(point, list):
                continue
            row_time = base_time + timedelta(seconds=idx * step)
            lat = point[lat_idx] if lat_idx is not None and lat_idx < len(point) else ""
            lon = point[lon_idx] if lon_idx is not None and lon_idx < len(point) else ""
            alt = (
                meters_to_feet(point[alt_idx])
                if alt_idx is not None and alt_idx < len(point) and point[alt_idx] is not None
                else ""
            )
            alt_b = (
                meters_to_feet(point[alt_raw_idx])
                if alt_raw_idx is not None and alt_raw_idx < len(point) and point[alt_raw_idx] is not None
                else alt
            )
            ias = point[ias_idx] if ias_idx is not None and ias_idx < len(point) else ""
            tas = point[tas_idx] if tas_idx is not None and tas_idx < len(point) else ""
            gs = point[gs_idx] if gs_idx is not None and gs_idx < len(point) else ""
            hdg = point[hdg_idx] if hdg_idx is not None and hdg_idx < len(point) else ""
            trk = point[trk_idx] if trk_idx is not None and trk_idx < len(point) else hdg
            pitch = point[pitch_idx] if pitch_idx is not None and pitch_idx < len(point) else ""
            roll = point[roll_idx] if roll_idx is not None and roll_idx < len(point) else ""
            vs = point[vs_idx] if vs_idx is not None and vs_idx < len(point) else ""
            if vs == "" and vs_knots_idx is not None and vs_knots_idx < len(point):
                vs_raw = point[vs_knots_idx]
                vs = knots_to_fpm(vs_raw) if vs_raw is not None else ""
            oat = point[oat_idx] if oat_idx is not None and oat_idx < len(point) else ""

            utc_offset = "+00:00"
            row = [""] * len(header_lines[-1].split(","))
            row[0] = fmt_date(row_time)
            row[1] = fmt_time(row_time)
            row[2] = utc_offset
            row[3] = lat
            row[4] = lon
            row[5] = alt
            row[6] = alt_b
            row[7] = ias
            row[8] = tas
            row[9] = gs
            row[10] = hdg if hdg != "" else trk
            row[11] = pitch
            row[12] = roll
            row[13] = vs
            row[14] = oat
            writer.writerow(row)


def write_points_garmin_g1000_csv(
    points: list,
    schema: list[dict[str, Any]],
    path: Path,
    start_time: datetime | None,
    step_seconds: float | None,
    metadata: dict[str, Any],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    schema_index = {column["name"]: column["index"] for column in schema}
    lat_idx = _index_for(schema, "latitude_deg", fallback=1)
    lon_idx = _index_for(schema, "longitude_deg", fallback=0)
    alt_idx = _index_for(schema, "alt_meters", fallback=2)
    alt_raw_idx = schema_index.get("alt_meters_raw")
    tas_idx = schema_index.get("tas_knots")
    ias_idx = schema_index.get("ias_knots")
    gs_idx = schema_index.get("gs_knots")
    trk_idx = schema_index.get("crs_degrees")
    hdg_idx = schema_index.get("heading_deg")
    vs_idx = schema_index.get("vs_fpm")
    vs_knots_idx = schema_index.get("vs_knots")
    roll_idx = schema_index.get("roll_deg")
    pitch_idx = schema_index.get("pitch_deg")
    oat_idx = schema_index.get("oat_c")

    gmt_epoch = _infer_gmt_epoch(start_time, metadata)
    base_time = datetime.fromtimestamp(gmt_epoch, tz=timezone.utc)
    step = step_seconds if step_seconds and step_seconds > 0 else 1.0
    stride = 1
    if step > 0 and step < 0.25:
        stride = max(1, int(math.ceil(0.25 / step)))

    def meters_to_feet(value: Any):
        return float(value) * 3.28084

    def knots_to_fpm(value: Any):
        return float(value) * 101.2686

    def fmt_date(ts: datetime) -> str:
        return ts.strftime("%Y-%m-%d")

    def fmt_time(ts: datetime) -> str:
        return ts.strftime("%H:%M:%S")

    airframe = metadata.get("aircraft_type") or "Unknown"
    tail = metadata.get("tail_number") or ""

    header_lines = [
        f"#airframe_info,1,{airframe},G1000,{tail}",
        "Lcl Date (yyyy-mm-dd),Lcl Time (hh:mm:ss),UTC Offset (hh:mm),Latitude (deg),Longitude (deg),"
        "AltB (ft),BaroA (ft),AltMSL (ft),OAT (C),IAS (kt),GndSpd (kt),VSpd (ft/min),Pitch (deg),"
        "Roll (deg),HDG (deg),TRK (deg),AltGPS (ft),TAS (kt)",
        "Lcl Date,Lcl Time,UTCOfst,Latitude,Longitude,AltB,BaroA,AltMSL,OAT,IAS,GndSpd,VSpd,"
        "Pitch,Roll,HDG,TRK,AltGPS,TAS",
    ]

    with path.open("w", newline="", encoding="utf-8") as handle:
        for line in header_lines:
            handle.write(f"{line}\n")
        writer = csv.writer(handle)
        for idx, point in enumerate(points):
            if idx % stride != 0:
                continue
            if not isinstance(point, list):
                continue
            row_time = base_time + timedelta(seconds=idx * step)
            lat = point[lat_idx] if lat_idx is not None and lat_idx < len(point) else ""
            lon = point[lon_idx] if lon_idx is not None and lon_idx < len(point) else ""
            alt_gps = (
                meters_to_feet(point[alt_idx])
                if alt_idx is not None and alt_idx < len(point) and point[alt_idx] is not None
                else ""
            )
            alt_b = (
                meters_to_feet(point[alt_raw_idx])
                if alt_raw_idx is not None and alt_raw_idx < len(point) and point[alt_raw_idx] is not None
                else alt_gps
            )
            ias = point[ias_idx] if ias_idx is not None and ias_idx < len(point) else ""
            tas = point[tas_idx] if tas_idx is not None and tas_idx < len(point) else ""
            gs = point[gs_idx] if gs_idx is not None and gs_idx < len(point) else ""
            hdg = point[hdg_idx] if hdg_idx is not None and hdg_idx < len(point) else ""
            trk = point[trk_idx] if trk_idx is not None and trk_idx < len(point) else hdg
            pitch = point[pitch_idx] if pitch_idx is not None and pitch_idx < len(point) else ""
            roll = point[roll_idx] if roll_idx is not None and roll_idx < len(point) else ""
            vs = point[vs_idx] if vs_idx is not None and vs_idx < len(point) else ""
            if vs == "" and vs_knots_idx is not None and vs_knots_idx < len(point):
                vs_raw = point[vs_knots_idx]
                vs = knots_to_fpm(vs_raw) if vs_raw is not None else ""
            oat = point[oat_idx] if oat_idx is not None and oat_idx < len(point) else ""

            utc_offset = "+00:00"
            row = [""] * len(header_lines[-1].split(","))
            row[0] = fmt_date(row_time)
            row[1] = fmt_time(row_time)
            row[2] = utc_offset
            row[3] = lat
            row[4] = lon
            row[5] = alt_b
            row[6] = alt_b
            row[7] = alt_b
            row[8] = oat
            row[9] = ias
            row[10] = gs
            row[11] = vs
            row[12] = pitch
            row[13] = roll
            row[14] = hdg
            row[15] = trk
            row[16] = alt_gps
            row[17] = tas
            writer.writerow(row)


def _infer_gmt_epoch(start_time: datetime | None, metadata: dict[str, Any]) -> int:
    if isinstance(start_time, datetime):
        return int(start_time.timestamp())
    summary = metadata.get("summary") if isinstance(metadata.get("summary"), dict) else None
    air = summary.get("air") if isinstance(summary, dict) else None
    air_start = air.get("start") if isinstance(air, dict) else None
    if air_start is not None:
        try:
            return int(float(air_start))
        except (TypeError, ValueError):
            pass
    return int(datetime.now(tz=timezone.utc).timestamp())


def _foreflight_metadata(metadata: dict[str, Any], gmt_epoch: int) -> list[tuple[str, str]]:
    lines: list[tuple[str, str]] = [("METADATA", "CA_CSV.3"), ("GMT", str(gmt_epoch))]
    tail = metadata.get("tail_number")
    if tail:
        lines.append(("TAIL", str(tail)))
    aircraft_type = metadata.get("aircraft_type")
    if aircraft_type:
        lines.append(("AIRCRAFT_TYPE", str(aircraft_type)))
    pilot_name, pilot_email = _extract_person(metadata.get("pilot"))
    if pilot_email:
        lines.append(("EMAIL", pilot_email))
    pilot = pilot_name
    if pilot:
        lines.append(("PILOT", pilot))
    copilot, _ = _extract_person(metadata.get("co_pilot"))
    if copilot:
        lines.append(("COPILOT", copilot))
    remarks = metadata.get("remarks")
    if remarks:
        lines.append(("Remarks", str(remarks)))
    tags = metadata.get("tags")
    if isinstance(tags, list) and tags:
        lines.append(("TAGS", ", ".join(str(tag) for tag in tags if tag)))
    is_sim = metadata.get("is_sim_flight")
    if is_sim is not None:
        lines.append(("ISSIM", "1" if is_sim else "0"))
    hobbs = metadata.get("hobbs")
    if hobbs:
        lines.append(("HOBBS", str(hobbs)))
    return lines


def _extract_person(value: Any) -> tuple[str | None, str | None]:
    if isinstance(value, list) and value:
        name = str(value[0]) if value[0] else None
        email = None
        if len(value) > 1 and value[1]:
            email = str(value[1])
        return name, email
    if isinstance(value, str) and value.strip():
        return value.strip(), None
    return None, None


def _foreflight_columns(
    schema_index: dict[str, int],
    alt_idx: int | None,
) -> list[tuple[str, Any]]:
    def pick_index(*names: str) -> int | None:
        for name in names:
            idx = schema_index.get(name)
            if idx is not None:
                return idx
        return None

    def from_idx(idx: int | None, transform=None):
        def _value(point: list, _row: int, _step: float):
            if idx is None or idx >= len(point):
                return ""
            value = point[idx]
            if value is None:
                return ""
            if transform:
                try:
                    return transform(value)
                except Exception:
                    return ""
            return value

        return _value

    def time_value(_point: list, row: int, step: float):
        return round(row * step, 3)

    def knots_to_fpm(value: Any):
        return float(value) * 101.2686

    def meters_to_feet(value: Any):
        return float(value) * 3.28084

    columns: list[tuple[str, Any]] = [
        ("seconds/t", time_value),
        ("degrees/lat", from_idx(schema_index.get("latitude_deg"))),
        ("degrees/lon", from_idx(schema_index.get("longitude_deg"))),
        ("feet/Alt (gps)", from_idx(alt_idx, meters_to_feet)),
    ]

    gs_idx = schema_index.get("gs_knots")
    if gs_idx is not None:
        columns.append(("knots/GS", from_idx(gs_idx)))
    tas_idx = schema_index.get("tas_knots")
    if tas_idx is not None:
        columns.append(("knots/TAS", from_idx(tas_idx)))
    ias_idx = schema_index.get("ias_knots")
    if ias_idx is not None:
        columns.append(("knots/IAS", from_idx(ias_idx)))

    trk_idx = pick_index("crs_degrees", "track_deg")
    hdg_idx = pick_index("heading_deg", "hdg_deg")
    if trk_idx is not None:
        columns.append(("degrees/TRK", from_idx(trk_idx)))
    elif hdg_idx is not None:
        columns.append(("degrees/TRK", from_idx(hdg_idx)))
    if hdg_idx is not None:
        columns.append(("degrees/HDG", from_idx(hdg_idx)))

    vs_idx = schema_index.get("vs_fpm")
    if vs_idx is not None:
        columns.append(("fpm/VS", from_idx(vs_idx)))
    else:
        vs_knots_idx = schema_index.get("vs_knots")
        if vs_knots_idx is not None:
            columns.append(("fpm/VS", from_idx(vs_knots_idx, knots_to_fpm)))

    roll_idx = schema_index.get("roll_deg")
    if roll_idx is not None:
        columns.append(("degrees/ROLL", from_idx(roll_idx)))

    pitch_idx = pick_index("pitch_deg", "pitch_degrees")
    if pitch_idx is not None:
        columns.append(("degrees/Pitch", from_idx(pitch_idx)))

    yaw_idx = pick_index("yaw_deg", "yaw_degrees")
    if yaw_idx is not None:
        columns.append(("degrees/Yaw", from_idx(yaw_idx)))

    mag_idx = schema_index.get("mag_variation_deg")
    if mag_idx is not None:
        columns.append(("degrees/MagVar", from_idx(mag_idx)))

    wind_spd_idx = schema_index.get("wind_speed_knots")
    if wind_spd_idx is not None:
        columns.append(("knots/WndSpd", from_idx(wind_spd_idx)))
    wind_dir_idx = schema_index.get("wind_dir_deg")
    if wind_dir_idx is not None:
        columns.append(("degrees/WndDr", from_idx(wind_dir_idx)))

    agl_idx = schema_index.get("agl_meters")
    if agl_idx is not None:
        columns.append(("feet/AGL", from_idx(agl_idx, meters_to_feet)))

    alt_msl_idx = schema_index.get("alt_meters_raw")
    if alt_msl_idx is not None:
        columns.append(("ft msl/AltMSL", from_idx(alt_msl_idx, meters_to_feet)))

    alt_baro_idx = schema_index.get("alt_meters_smooth")
    if alt_baro_idx is not None:
        columns.append(("ft baro/AltB", from_idx(alt_baro_idx, meters_to_feet)))

    return columns


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
