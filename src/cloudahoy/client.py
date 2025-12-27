from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.cloudahoy.points import (
    build_points_schema,
    write_points_gpx,
    write_points_csv,
    write_points_flightradar24_csv,
    write_points_garmin_g3x_csv,
    write_points_garmin_g1000_csv,
    write_points_mvp50_csv,
    write_points_foreflight_csv,
)
from src.models import FlightDetail, FlightSummary
import json
import string


@dataclass(frozen=True)
class CloudAhoyClient:
    api_key: str | None
    base_url: str
    email: str
    password: str
    exports_dir: Path
    export_format: str = "gpx"

    def list_flights(self, limit: int | None = None) -> list[FlightSummary]:
        session, auth = _login(self.email, self.password)
        payload = _build_auth_payload(auth, initial_call=True)
        flights: list[dict] = []
        more = True
        last_token = None
        safety = 0

        while more:
            response = session.post(
                f"{_api_base(self.base_url)}/t-flights.cgi",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
            batch = data.get("flights", [])
            if isinstance(batch, list):
                flights.extend(batch)

            more = bool(data.get("more"))
            last_token = _extract_last_token(batch)
            if not last_token:
                more = False

            if limit and len(flights) >= limit:
                flights = flights[:limit]
                break

            safety += 1
            if not more or safety > 20:
                break

            payload = _build_auth_payload(auth, initial_call=False)
            payload["last"] = last_token

        summaries: list[FlightSummary] = []
        seen: set[str] = set()
        for flight in flights[: limit or len(flights)]:
            flight_id = flight.get("key") or flight.get("fdID")
            if not flight_id or flight_id in seen:
                continue
            seen.add(flight_id)
            started_at = _from_unix(flight.get("gmtStart") or flight.get("adjTime"))
            summaries.append(
                FlightSummary(
                    id=flight_id,
                    started_at=started_at,
                    duration_seconds=flight.get("nSec"),
                    aircraft_type=flight.get("aircraft", {}).get("P", {}).get("typeAircraft"),
                    tail_number=flight.get("tailNumber") or flight.get("aircraft", {}).get("tailNumber"),
                )
            )
        return summaries

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        data = self._fetch_raw(flight_id)

        flt = data.get("flt", {})
        points = flt.get("points") if isinstance(flt, dict) else None
        file_path = None
        file_type = None
        metadata_path = None
        csv_path = None
        raw_path = None
        metadata = _extract_metadata(flt)
        self.exports_dir.mkdir(parents=True, exist_ok=True)
        raw_path = self.exports_dir / f"{flight_id}.cloudahoy.json"
        raw_path.write_text(json.dumps(data, indent=2))
        if isinstance(points, list) and points:
            schema = build_points_schema(flt)
            if schema:
                start_time, step_seconds = _infer_point_timing(flt, len(points))
                file_path = self.exports_dir / f"{flight_id}.gpx"
                write_points_gpx(
                    points,
                    schema,
                    file_path,
                    start_time=start_time,
                    step_seconds=step_seconds,
                    track_name=flight_id,
                )
                export_formats = (
                    [fmt.lower() for fmt in self.export_formats]
                    if self.export_formats
                    else [self.export_format.lower()]
                )
                export_formats = [fmt if fmt != "cloudahoy" else "gpx" for fmt in export_formats]
                if "gpx" not in export_formats:
                    export_formats.append("gpx")
                export_paths: dict[str, Path] = {"gpx": file_path}

                for fmt in export_formats:
                    if fmt == "gpx":
                        continue
                    csv_suffix = _csv_suffix(fmt)
                    csv_path = self.exports_dir / f"{flight_id}{csv_suffix}.csv"
                    if fmt == "foreflight":
                        write_points_foreflight_csv(
                            points,
                            schema,
                            csv_path,
                            start_time=start_time,
                            step_seconds=step_seconds,
                            metadata=metadata,
                        )
                    elif fmt in {"flightradar24", "fr24"}:
                        write_points_flightradar24_csv(
                            points,
                            schema,
                            csv_path,
                            start_time=start_time,
                            step_seconds=step_seconds,
                            metadata=metadata,
                        )
                    elif fmt in {"mvp50", "mvp-50", "mvp50t", "mvp50p"}:
                        write_points_mvp50_csv(
                            points,
                            schema,
                            csv_path,
                            start_time=start_time,
                            step_seconds=step_seconds,
                            metadata=metadata,
                        )
                    elif fmt in {"garmin_g3x", "g3x", "garmin-g3x"}:
                        write_points_garmin_g3x_csv(
                            points,
                            schema,
                            csv_path,
                            start_time=start_time,
                            step_seconds=step_seconds,
                            metadata=metadata,
                        )
                    elif fmt in {"garmin_g1000", "g1000", "garmin-g1000"}:
                        write_points_garmin_g1000_csv(
                            points,
                            schema,
                            csv_path,
                            start_time=start_time,
                            step_seconds=step_seconds,
                            metadata=metadata,
                        )
                    else:
                        write_points_csv(points, schema, csv_path)
                    export_paths[fmt] = csv_path

                def fmt_rank(name: str) -> int:
                    order = [
                        "g3x",
                        "garmin-g3x",
                        "garmin_g3x",
                        "g1000",
                        "garmin-g1000",
                        "garmin_g1000",
                        "foreflight",
                        "flightradar24",
                        "fr24",
                        "mvp50",
                        "mvp-50",
                        "mvp50t",
                        "mvp50p",
                        "gpx",
                    ]
                    try:
                        return order.index(name)
                    except ValueError:
                        return len(order) + 1

                preferred = None
                for key in sorted(export_paths.keys(), key=fmt_rank):
                    preferred = key
                    break
                export_format = preferred or "gpx"

                file_type = "gpx"
                if export_format and export_format != "gpx":
                    file_path = export_paths.get(export_format, file_path)
                    file_type = export_format
                    csv_path = export_paths.get(export_format)
        if not file_path:
            kml_text = _extract_kml(data)
            if kml_text:
                file_path = self.exports_dir / f"{flight_id}.kml"
                file_path.write_text(kml_text)
                file_type = "kml"
        if metadata:
            metadata_path = self.exports_dir / f"{flight_id}.meta.json"
            metadata_path.write_text(json.dumps(metadata, indent=2))

        return FlightDetail(
            id=flight_id,
            raw_payload=data,
            raw_path=str(raw_path) if raw_path else None,
            file_path=str(file_path) if file_path else None,
            file_type=file_type,
            metadata_path=str(metadata_path) if metadata_path else None,
            csv_path=str(csv_path) if csv_path else None,
            export_paths={key: str(value) for key, value in export_paths.items()}
            if "export_paths" in locals()
            else None,
        )

    def fetch_metadata(self, flight_id: str) -> dict:
        data = self._fetch_raw(flight_id)
        flt = data.get("flt", {})
        return _extract_metadata(flt)

    def _fetch_raw(self, flight_id: str) -> dict:
        session, auth = _login(self.email, self.password)
        payload = _build_auth_payload(auth, initial_call=False)
        payload["flight"] = flight_id
        response = session.post(
            f"{_api_base(self.base_url)}/t-debrief.cgi",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        return response.json()


def _csv_suffix(export_format: str) -> str:
    if not export_format or export_format == "gpx":
        return ""
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in export_format)
    return f".{safe}"


def _login(email: str, password: str) -> tuple[requests.Session, dict]:
    session = requests.Session()
    response = session.post(
        "https://www.cloudahoy.com/api/signin.cgi?form",
        data={"email": email, "password": password},
        timeout=60,
    )
    response.raise_for_status()
    auth = {
        "SID3": _extract_cookie(response.text, "SID3"),
        "USER3": _extract_cookie(response.text, "USER3"),
        "EMAIL3": _extract_cookie(response.text, "EMAIL3"),
    }
    if not all(auth.values()):
        raise RuntimeError("CloudAhoy login failed: session cookies not found.")
    for key, value in auth.items():
        session.cookies.set(key, value, domain="www.cloudahoy.com", path="/")
    return session, auth


def _extract_cookie(html: str, name: str) -> str | None:
    needle = f'setCookie("{name}","'
    start = html.find(needle)
    if start == -1:
        return None
    start += len(needle)
    end = html.find('"', start)
    if end == -1:
        return None
    return html[start:end]


def _build_auth_payload(auth: dict, initial_call: bool) -> dict:
    return {
        "userName": False,
        "initialCall": initial_call,
        "EMAIL3": auth.get("EMAIL3"),
        "SID3": auth.get("SID3"),
        "STLI": None,
        "USER3": auth.get("USER3"),
        "BI": f"CLI{int(datetime.now(tz=timezone.utc).timestamp())}",
        "PH": {"n": [], "t": []},
        "wlh": "https://www.cloudahoy.com/debrief/" if not initial_call else "https://www.cloudahoy.com/flights/",
    }


def _from_unix(value: int | float | None) -> datetime:
    if value is None:
        return datetime.now(tz=timezone.utc)
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(tz=timezone.utc)


def _infer_point_timing(flt: dict, points_count: int) -> tuple[datetime | None, float | None]:
    meta = flt.get("Meta") if isinstance(flt, dict) else None
    if not isinstance(meta, dict):
        return None, None
    start_time = None
    start = meta.get("GMT_start")
    try:
        if start is not None:
            start_time = datetime.fromtimestamp(float(start), tz=timezone.utc)
    except (TypeError, ValueError):
        start_time = None

    air_hours = meta.get("air")
    gnd_hours = meta.get("gnd")
    if start_time and (air_hours is not None or gnd_hours is not None):
        try:
            total_hours = float(air_hours or 0) + float(gnd_hours or 0)
            if total_hours > 0 and points_count > 1:
                step = (total_hours * 3600) / (points_count - 1)
                if step > 0 and step <= 30:
                    return start_time, step
        except (TypeError, ValueError):
            pass

    summary = meta.get("summary") if isinstance(meta.get("summary"), dict) else None
    air = summary.get("air") if isinstance(summary, dict) else None
    air_start = air.get("start") if isinstance(air, dict) else None
    air_end = air.get("end") if isinstance(air, dict) else None
    if air_start is not None and air_end is not None:
        try:
            air_start_ts = float(air_start)
            air_end_ts = float(air_end)
            if air_end_ts > air_start_ts:
                start_time = datetime.fromtimestamp(air_start_ts, tz=timezone.utc)
                duration_seconds = air_end_ts - air_start_ts
                if points_count > 1:
                    step = duration_seconds / (points_count - 1)
                    if step > 0 and step <= 30:
                        return start_time, step
        except (TypeError, ValueError):
            start_time = None
    duration_hours = None
    air = meta.get("air")
    gnd = meta.get("gnd")
    try:
        if air is not None or gnd is not None:
            duration_hours = float(air or 0) + float(gnd or 0)
    except (TypeError, ValueError):
        duration_hours = None
    if duration_hours is None or points_count <= 1:
        return start_time, None
    duration_seconds = duration_hours * 3600
    if duration_seconds <= 0:
        return start_time, None
    step = duration_seconds / (points_count - 1)
    if step <= 0 or step > 30:
        return start_time, None
    return start_time, step



def _extract_kml(payload: dict) -> str | None:
    flt = payload.get("flt", {})
    kml = flt.get("KML")
    if isinstance(kml, dict):
        for value in kml.values():
            if isinstance(value, str) and value.lstrip().startswith("<?xml"):
                return value
    if isinstance(kml, str) and kml.lstrip().startswith("<?xml"):
        return kml
    return None


def _api_base(base_url: str) -> str:
    if "api.cloudahoy.com" in base_url:
        return "https://www.cloudahoy.com/api"
    return base_url.rstrip("/")


def _extract_last_token(flights: list[dict]) -> str | None:
    if not flights:
        return None
    last = flights[-1]
    gmt_start = last.get("gmtStart") or last.get("adjTime")
    if gmt_start is None:
        return None
    try:
        gmt_start = int(float(gmt_start))
    except (TypeError, ValueError):
        return None
    return f"zz14[d-mmm-yy HH:MM]{gmt_start}zz14"


def _extract_metadata(flt: dict) -> dict:
    meta = flt.get("Meta") if isinstance(flt, dict) else None
    if not isinstance(meta, dict):
        return {}
    tail_number, aircraft_type, tail_raw = _normalize_tail_number(meta.get("tailNumber"))
    fields = {
        "pilot": meta.get("pilot"),
        "co_pilot": meta.get("coPilot"),
        "pilots": meta.get("pilots"),
        "remarks": meta.get("remarks"),
        "tags": meta.get("tags"),
        "tail_number": tail_number,
        "tail_number_raw": tail_raw,
        "aircraft_type": aircraft_type,
        "aircraft_from": meta.get("from"),
        "aircraft_to": meta.get("to"),
        "event_from": meta.get("e_from"),
        "event_to": meta.get("e_to"),
        "is_sim_flight": meta.get("isSimFlight"),
        "summary": meta.get("summary"),
        "hobbs": meta.get("hobbs"),
    }
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


def _normalize_tail_number(value: object) -> tuple[str | None, str | None, list[str] | None]:
    if isinstance(value, str):
        tail = value.strip()
        if _is_placeholder(tail):
            return None, None, [tail]
        return tail, None, None
    if isinstance(value, list):
        tail_candidates = [v for v in value if isinstance(v, str)]
        tail_raw = [v for v in tail_candidates if v]
        tail_number = None
        aircraft_type = None
        for entry in tail_candidates:
            if _is_tail_candidate(entry):
                tail_number = entry
                break
        for entry in tail_candidates:
            if _is_placeholder(entry):
                continue
            if tail_number and entry == tail_number:
                continue
            if not _is_tail_candidate(entry):
                aircraft_type = entry
                break
        return tail_number, aircraft_type, tail_raw or None
    return None, None, None


def _is_tail_candidate(value: str) -> bool:
    stripped = value.strip()
    if _is_placeholder(stripped):
        return False
    if len(stripped) < 2 or len(stripped) > 12:
        return False
    if not all(ch in (string.ascii_letters + string.digits + "-") for ch in stripped):
        return False
    if not any(ch.isdigit() for ch in stripped):
        if not _matches_tail_pattern(stripped):
            return False
    return True


def _is_placeholder(value: str) -> bool:
    return value.strip().upper() in {"", "OTHER", "UNKNOWN"}


def _matches_tail_pattern(value: str) -> bool:
    if "-" not in value:
        return False
    prefix, suffix = value.split("-", 1)
    if not prefix or not suffix:
        return False
    if len(prefix) > 2:
        return False
    if not prefix.isalpha():
        return False
    if not all(ch.isalnum() for ch in suffix):
        return False
    return True
