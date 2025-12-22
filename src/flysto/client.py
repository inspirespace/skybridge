from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Any
import zipfile
from urllib.parse import urljoin, urlparse

import requests

from src.models import FlightDetail


@dataclass
class FlyStoClient:
    api_key: str
    base_url: str
    upload_url: str | None = None
    session_cookie: str | None = None
    include_metadata: bool = False
    api_version: str | None = None
    email: str | None = None
    password: str | None = None
    aircraft_profiles_cache: list[dict[str, Any]] | None = None
    aircraft_cache: list[dict[str, Any]] | None = None
    assigned_avionics: set[tuple[str, str | None]] | None = None

    def prepare(self) -> bool:
        session = requests.Session()
        try:
            self._ensure_session(session)
        except Exception:
            return False
        cookie = session.cookies.get("USER_SESSION") or self.session_cookie
        if not cookie:
            return False
        self.session_cookie = cookie
        if not self.api_version:
            self.api_version = _infer_api_version(self.base_url)
        return True

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> None:
        if dry_run:
            _validate_flight_for_upload(flight)
            return
        _validate_flight_for_upload(flight)
        session = requests.Session()
        self._ensure_session(session)
        if not self.api_version:
            self.api_version = _infer_api_version(self.base_url)

        file_path = Path(flight.file_path)
        payload = _build_upload_payload(file_path)
        headers = {"content-type": "application/zip"}
        if self.api_version:
            headers["x-version"] = self.api_version
        response = session.post(
            _upload_url(self.upload_url, self.base_url, file_path.name),
            data=payload,
            headers=headers,
            timeout=120,
        )

        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto upload failed: {response.status_code} {response.text[:300]}"
            )


    def ensure_aircraft(self, tail_number: str | None, aircraft_type: str | None = None) -> dict[str, Any] | None:
        if not tail_number:
            return None
        session = requests.Session()
        self._ensure_session(session)
        existing = self._find_aircraft_by_tail(session, tail_number)
        if existing:
            return existing
        model_id = self._match_model_id(aircraft_type)
        if not model_id:
            raise RuntimeError("Unable to infer FlySto aircraft model for tail number.")
        payload = {
            "avionics": {"logFormatId": "gpx", "systemId": "gpx"},
            "tailNumber": tail_number,
            "serialNumber": None,
            "notes": None,
            "model": {
                "type": "flysto.webapi.AircraftModel.Predefined",
                "modelId": model_id,
            },
            "logAccess": "AuthorizedUserOnly",
        }
        response = session.post(
            self.base_url.rstrip("/") + "/api/create-aircraft",
            json=payload,
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto create-aircraft failed: {response.status_code} {response.text[:200]}"
            )
        # refresh cache
        self.aircraft_cache = None
        return self._find_aircraft_by_tail(session, tail_number)

    def _find_aircraft_by_tail(self, session: requests.Session, tail_number: str) -> dict[str, Any] | None:
        aircraft = self._list_aircraft(session)
        for entry in aircraft:
            if entry.get("tail-number") == tail_number:
                return entry
        return None

    def _list_aircraft(self, session: requests.Session) -> list[dict[str, Any]]:
        if self.aircraft_cache is not None:
            return self.aircraft_cache
        response = session.get(self.base_url.rstrip("/") + "/api/aircraft", timeout=60)
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = []
        elif isinstance(decoded, list):
            data = decoded
        else:
            data = []
        self.aircraft_cache = data if isinstance(data, list) else []
        return self.aircraft_cache

    def _match_model_id(self, aircraft_type: str | None) -> str | None:
        profiles = self._list_aircraft_profiles()
        if not profiles:
            return None
        if aircraft_type:
            needle = aircraft_type.strip().lower()
            for profile in profiles:
                name = (profile.get("modelName") or "").lower()
                search = " ".join(profile.get("searchNames") or []).lower()
                if needle in name or needle in search:
                    return profile.get("modelId")
        # Prefer a generic "Other" model when present.
        for profile in profiles:
            name = (profile.get("modelName") or "").strip().lower()
            if name == "other" or name.startswith("other "):
                return profile.get("modelId")
        # fallback to first known model
        return profiles[0].get("modelId") or "Other"

    def _list_aircraft_profiles(self) -> list[dict[str, Any]]:
        if self.aircraft_profiles_cache is not None:
            return self.aircraft_profiles_cache
        response = requests.get(self.base_url.rstrip("/") + "/api/aircraft-profiles", timeout=60)
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = []
        elif isinstance(decoded, list):
            data = decoded
        else:
            data = []
        self.aircraft_profiles_cache = data if isinstance(data, list) else []
        return self.aircraft_profiles_cache


    def assign_aircraft(
        self,
        aircraft_id: str,
        log_format_id: str = "GenericGpx",
        system_id: str | None = None,
    ) -> None:
        if not aircraft_id:
            return
        key = (log_format_id, system_id)
        if self.assigned_avionics is None:
            self.assigned_avionics = set()
        if key in self.assigned_avionics:
            return
        session = requests.Session()
        self._ensure_session(session)
        payload = {
            "avionics": {"logFormatId": log_format_id, "systemId": system_id},
            "aircraftIdString": aircraft_id,
        }
        response = session.post(
            self.base_url.rstrip("/") + "/api/assign-aircraft",
            json=payload,
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto assign-aircraft failed: {response.status_code} {response.text[:200]}"
            )
        self.assigned_avionics.add(key)

    def _ensure_session(self, session: requests.Session) -> None:
        if self.session_cookie:
            hostname = urlparse(self.base_url).hostname or "www.flysto.net"
            session.cookies.set(
                "USER_SESSION",
                self.session_cookie,
                domain=hostname,
                path="/",
            )
            return
        if self.email and self.password:
            _api_login(session, self.base_url, self.email, self.password, self.api_version)
            cookie = session.cookies.get("USER_SESSION")
            if not cookie:
                raise RuntimeError("FlySto API login returned no session cookie.")
            return
        raise NotImplementedError("FlySto API auth not configured.")




def _decode_flysto_payload(text: str) -> Any:
    if text.startswith("wait\n"):
        text = text.split("\n", 1)[1]
    if text.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(data, dict) and "RESPONSE" in data:
            decoded = _swap_chars(str(data.get("RESPONSE", "")))
            return decoded
        return data
    return text


def _swap_chars(value: str) -> str:
    chars: list[str] = []
    for ch in value:
        code = ord(ch)
        if 32 <= code <= 127:
            chars.append(chr((127 - code) + 32))
        else:
            chars.append(ch)
    return "".join(chars)
def _validate_flight_for_upload(flight: FlightDetail) -> None:
    if not flight.file_path:
        raise RuntimeError("Flight export file is required for FlySto upload.")
    path = Path(flight.file_path)
    if not path.exists():
        raise RuntimeError("Flight export file missing on disk.")




def _build_upload_payload(path: Path) -> bytes:
    data = path.read_bytes()
    if path.suffix.lower() == ".zip":
        return data
    buffer = __import__('io').BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(path.name, data)
    return buffer.getvalue()

def _metadata_payload(flight: FlightDetail) -> dict:
    payload = flight.raw_payload.get("flt", {}).get("Meta", {})
    if not isinstance(payload, dict):
        return {}
    return payload


def _upload_url(upload_url: str | None, base_url: str, filename: str) -> str:
    url = upload_url or (base_url.rstrip("/") + "/api/log-upload")
    if "?" in url:
        return url
    return f"{url}?id={filename}@@@0"


def _api_login(
    session: requests.Session,
    base_url: str,
    email: str,
    password: str,
    api_version: str | None,
) -> None:
    url = base_url.rstrip("/") + "/api/login"
    headers = {"content-type": "text/plain;charset=UTF-8"}
    if api_version:
        headers["x-version"] = api_version
    payload = json.dumps({"email": email, "password": password})
    response = session.post(url, data=payload, headers=headers, timeout=60)
    if response.status_code >= 300:
        raise RuntimeError(f"FlySto API login failed: {response.status_code}")


def _infer_api_version(base_url: str) -> str | None:
    candidates: list[str] = []
    base = base_url.rstrip("/") + "/"
    candidates.append(urljoin(base, "login"))
    if "api.flysto.net" in base_url:
        candidates.append("https://www.flysto.net/login")
    elif "flysto.net" in base_url and "www.flysto.net" not in base_url:
        candidates.append("https://www.flysto.net/login")
    for login_url in candidates:
        try:
            login = requests.get(login_url, timeout=30)
            login.raise_for_status()
            match = re.search(r"/static/(flysto\\.[^\\\"']+\\.js)", login.text)
            if not match:
                continue
            base_root = "{uri.scheme}://{uri.netloc}/".format(
                uri=urlparse(login_url)
            )
            bundle_url = urljoin(base_root, f"static/{match.group(1)}")
            bundle = requests.get(bundle_url, timeout=30)
            bundle.raise_for_status()
            match = re.search(r"x-version\"\\s*[:,]\\s*\"?(\\d+)\"?", bundle.text)
            if match:
                return match.group(1)
        except Exception:
            continue
    return None
