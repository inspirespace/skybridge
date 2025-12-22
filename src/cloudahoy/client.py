from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.models import FlightDetail, FlightSummary


@dataclass(frozen=True)
class CloudAhoyClient:
    api_key: str | None
    base_url: str
    email: str
    password: str
    exports_dir: Path

    def list_flights(self, limit: int | None = None) -> list[FlightSummary]:
        session, auth = _login(self.email, self.password)
        payload = _build_auth_payload(auth, initial_call=True)
        response = session.post(
            f"{_api_base(self.base_url)}/t-flights.cgi",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        flights = data.get("flights", [])

        summaries: list[FlightSummary] = []
        for flight in flights[: limit or len(flights)]:
            started_at = _from_unix(flight.get("gmtStart") or flight.get("adjTime"))
            summaries.append(
                FlightSummary(
                    id=flight.get("key") or flight.get("fdID"),
                    started_at=started_at,
                    duration_seconds=flight.get("nSec"),
                    aircraft_type=flight.get("aircraft", {}).get("P", {}).get("typeAircraft"),
                    tail_number=flight.get("tailNumber") or flight.get("aircraft", {}).get("tailNumber"),
                )
            )
        return summaries

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        session, auth = _login(self.email, self.password)
        payload = _build_auth_payload(auth, initial_call=False)
        payload["flight"] = flight_id
        response = session.post(
            f"{_api_base(self.base_url)}/t-debrief.cgi",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        kml_text = _extract_kml(data)
        file_path = None
        if kml_text:
            self.exports_dir.mkdir(parents=True, exist_ok=True)
            file_path = self.exports_dir / f"{flight_id}.kml"
            file_path.write_text(kml_text)

        return FlightDetail(
            id=flight_id,
            raw_payload=data,
            file_path=str(file_path) if file_path else None,
            file_type="kml" if file_path else None,
        )


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
