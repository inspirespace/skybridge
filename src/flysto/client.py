from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
import time
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
    crew_cache: list[dict[str, Any]] | None = None
    crew_roles_cache: list[dict[str, Any]] | None = None
    min_request_interval: float = 0.5
    max_request_retries: int = 3
    _last_request_at: float | None = None

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
        response = self._request(
            session,
            "post",
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
        response = self._request(
            session,
            "post",
            self.base_url.rstrip("/") + "/api/create-aircraft",
            json=payload,
            timeout=60,
        )
        if response.status_code >= 300 and model_id != "Other":
            payload["model"]["modelId"] = "Other"
            response = self._request(
                session,
                "post",
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
            if entry.get("tail-number") == tail_number or entry.get("tailNumber") == tail_number:
                return entry
        return None

    def _list_aircraft(self, session: requests.Session) -> list[dict[str, Any]]:
        if self.aircraft_cache is not None:
            return self.aircraft_cache
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/aircraft",
            timeout=60,
        )
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
            target = aircraft_type.strip().lower()
            for profile in profiles:
                name = (profile.get("modelName") or "").strip().lower()
                if name == target:
                    return profile.get("modelId")
        return profiles[0].get("modelId")

    def _list_aircraft_profiles(self) -> list[dict[str, Any]]:
        if self.aircraft_profiles_cache is not None:
            return self.aircraft_profiles_cache
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/aircraft-profiles",
            timeout=60,
        )
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
        headers = {"content-type": "text/plain;charset=UTF-8"}
        if self.api_version:
            headers["x-version"] = self.api_version
        response = self._request(
            session,
            "post",
            self.base_url.rstrip("/") + "/api/assign-aircraft",
            data=json.dumps(payload),
            headers=headers,
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto assign-aircraft failed: {response.status_code} {response.text[:200]}"
            )
        self.assigned_avionics.add(key)


    def resolve_log_for_file(
        self,
        filename: str,
        retries: int = 8,
        delay_seconds: float = 3.0,
    ) -> tuple[str | None, str | None, str | None]:
        session = requests.Session()
        self._ensure_session(session)
        keys = "57,tf,ec,hq,86,b2,lb,8q,p2,85,bl,hk,4n,ee,yu,1y,t3,ng,ho,hq,x9,g3,6n,hq,0s,83,6h,am"
        for attempt in range(retries):
            params = {"type": "flight", "logs": 250, "order": "descending"}
            response = self._request(
                session,
                "get",
                self.base_url.rstrip("/") + "/api/log-list",
                params=params,
                timeout=60,
            )
            decoded = _decode_flysto_payload(response.text)
            if isinstance(decoded, str):
                try:
                    log_ids = json.loads(decoded)
                except json.JSONDecodeError:
                    log_ids = []
            elif isinstance(decoded, list):
                log_ids = decoded
            else:
                log_ids = []
            log_ids = [str(log_id) for log_id in log_ids]
            if not log_ids:
                if attempt < retries - 1:
                    time.sleep(delay_seconds * (attempt + 1))
                    continue
                return None, None, None
            summary = self._request(
                session,
                "get",
                self.base_url.rstrip("/") + "/api/log-summary",
                params={"logs": ",".join(log_ids), "keys": keys, "update": "false"},
                timeout=60,
            )
            decoded = _decode_flysto_payload(summary.text)
            if isinstance(decoded, str):
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    data = None
            elif isinstance(decoded, dict):
                data = decoded
            else:
                data = None
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                summary_data = item.get("summary", {}).get("data", {})
                files = summary_data.get("t3") or []
                for entry in files:
                    if entry.get("file") == filename:
                        signature = summary_data.get("6h")
                        log_format = entry.get("format")
                        return str(item.get("id")), signature, log_format
            if attempt < retries - 1:
                time.sleep(delay_seconds * (attempt + 1))
        # Final attempt with update=true to refresh summaries.
        if log_ids:
            summary = self._request(
                session,
                "get",
                self.base_url.rstrip("/") + "/api/log-summary",
                params={"logs": ",".join(log_ids), "keys": keys, "update": "true"},
                timeout=60,
            )
            decoded = _decode_flysto_payload(summary.text)
            if isinstance(decoded, str):
                try:
                    data = json.loads(decoded)
                except json.JSONDecodeError:
                    data = None
            elif isinstance(decoded, dict):
                data = decoded
            else:
                data = None
            items = data.get("items", []) if isinstance(data, dict) else []
            for item in items:
                summary_data = item.get("summary", {}).get("data", {})
                files = summary_data.get("t3") or []
                for entry in files:
                    if entry.get("file") == filename:
                        signature = summary_data.get("6h")
                        log_format = entry.get("format")
                        return str(item.get("id")), signature, log_format
        return None, None, None

    def assign_aircraft_for_file(
        self,
        filename: str,
        aircraft_id: str,
        log_format_id: str = "GenericGpx",
    ) -> None:
        log_id, signature, resolved_format = self.resolve_log_for_file(filename)
        if not signature:
            return
        effective_format = resolved_format or log_format_id
        self.assign_aircraft(aircraft_id, log_format_id=effective_format, system_id=signature)

    def assign_crew_for_file(self, filename: str, crew: list[dict[str, Any]]) -> None:
        if not crew:
            return
        log_id, _signature, _format = self.resolve_log_for_file(filename)
        if not log_id:
            return
        names: list[str] = []
        roles: list[str] = []
        crew_names = [entry.get("name") for entry in crew if entry.get("name")]
        self._ensure_crew_members([name for name in crew_names if isinstance(name, str)])
        default_role_id = self._default_role_id()
        for entry in crew:
            name = entry.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            role_name = entry.get("role")
            role_id = self._resolve_role_id(role_name, bool(entry.get("is_pic")))
            if not role_id:
                role_id = default_role_id
            if not role_id:
                continue
            names.append(name.strip())
            roles.append(role_id)
        if not names or not roles:
            return
        self._assign_crew([log_id], names, roles)

    def _assign_crew(self, log_ids: list[str], names: list[str], roles: list[str]) -> None:
        if not log_ids or not names or not roles:
            return
        if len(names) != len(roles):
            raise ValueError("FlySto crew assignment requires matching names and roles length.")
        session = requests.Session()
        self._ensure_session(session)
        payload = {"logIds": log_ids, "names": names, "roles": roles}
        response = self._request(
            session,
            "post",
            self.base_url.rstrip("/") + "/api/assign-crew",
            json=payload,
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto assign-crew failed: {response.status_code} {response.text[:200]}"
            )

    def _ensure_crew_members(self, names: list[str]) -> None:
        clean = sorted({name.strip() for name in names if name and isinstance(name, str)})
        if not clean:
            return
        existing = {self._crew_name(entry) for entry in self._list_crew() if self._crew_name(entry)}
        missing = [name for name in clean if name not in existing]
        if not missing:
            return
        session = requests.Session()
        self._ensure_session(session)
        for name in missing:
            response = self._request(
                session,
                "post",
                self.base_url.rstrip("/") + "/api/new-crew",
                json={"name": name},
                timeout=60,
            )
            if response.status_code >= 300:
                raise RuntimeError(
                    f"FlySto create-crew failed: {response.status_code} {response.text[:200]}"
                )
        self.crew_cache = None

    def _list_crew(self) -> list[dict[str, Any]]:
        if self.crew_cache is not None:
            return self.crew_cache
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/user-crew",
            timeout=60,
        )
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = []
        elif isinstance(decoded, list):
            data = decoded
        else:
            data = decoded.get("items", []) if isinstance(decoded, dict) else []
        self.crew_cache = data if isinstance(data, list) else []
        return self.crew_cache

    def _crew_name(self, entry: dict[str, Any]) -> str | None:
        for key in ("name", "fullName", "crewName"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _list_crew_roles(self) -> list[dict[str, Any]]:
        if self.crew_roles_cache is not None:
            return self.crew_roles_cache
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/user-crew-roles",
            timeout=60,
        )
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = []
        elif isinstance(decoded, list):
            data = decoded
        else:
            data = decoded.get("items", []) if isinstance(decoded, dict) else []
        self.crew_roles_cache = data if isinstance(data, list) else []
        return self.crew_roles_cache

    def _default_role_id(self) -> str | None:
        roles = self._list_crew_roles()
        if not roles:
            return None
        preferred = ["pic", "pilot in command", "pilot"]
        for role in roles:
            role_id, role_name = self._role_id_name(role)
            if not role_id or not role_name:
                continue
            if _normalize_role(role_name) in {_normalize_role(value) for value in preferred}:
                return role_id
        role_id, _name = self._role_id_name(roles[0])
        return role_id

    def _resolve_role_id(self, role_name: str | None, is_pic: bool) -> str | None:
        roles = self._list_crew_roles()
        if not roles:
            return None
        candidates = []
        if is_pic:
            candidates.extend(["PIC", "Pilot in command"])
        if role_name:
            candidates.append(role_name)
        if role_name:
            role_lower = role_name.strip().lower()
            if role_lower in {"co-pilot", "copilot", "co pilot"}:
                candidates.extend(["Copilot", "Co-pilot", "Co pilot"])
            elif role_lower in {"safety pilot", "safety"}:
                candidates.append("Safety pilot")
            elif role_lower in {"instructor", "cfi", "cfii"}:
                candidates.append("Instructor")
            elif role_lower in {"student", "trainee"}:
                candidates.append("Student")
            elif role_lower in {"pilot"} and not is_pic:
                # Prefer non-PIC pilot roles when available.
                candidates.append("Pilot")
        candidate_norm = {_normalize_role(value) for value in candidates if value}
        for role in roles:
            role_id, name = self._role_id_name(role)
            if not role_id or not name:
                continue
            if _normalize_role(name) in candidate_norm:
                return role_id
        if role_name and role_name.strip().lower() == "pilot" and not is_pic:
            for role in roles:
                role_id, name = self._role_id_name(role)
                if not role_id or not name:
                    continue
                if _normalize_role(name) in {_normalize_role("Copilot"), _normalize_role("Co-pilot")}:
                    return role_id
        return None

    def _role_id_name(self, role: dict[str, Any]) -> tuple[str | None, str | None]:
        role_id = role.get("id") or role.get("crewRoleId") or role.get("roleId")
        name = role.get("name") or role.get("crewRoleName") or role.get("roleName")
        role_id = str(role_id) if role_id is not None else None
        if isinstance(name, str):
            name = name.strip()
        return role_id, name if isinstance(name, str) else None

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

    def _request(self, session: requests.Session, method: str, url: str, **kwargs) -> requests.Response:
        method = method.lower()
        last_error = None
        for attempt in range(self.max_request_retries):
            self._respect_rate_limit()
            try:
                response = session.request(method, url, **kwargs)
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(self._retry_delay(attempt))
                continue
            if response.status_code in {429, 502, 503, 504}:
                time.sleep(self._retry_delay(attempt))
                continue
            return response
        if last_error:
            raise last_error
        return response

    def _respect_rate_limit(self) -> None:
        if self.min_request_interval <= 0:
            return
        now = time.monotonic()
        if self._last_request_at is None:
            self._last_request_at = now
            return
        elapsed = now - self._last_request_at
        if elapsed < self.min_request_interval:
            time.sleep(self.min_request_interval - elapsed)
        self._last_request_at = time.monotonic()

    def _retry_delay(self, attempt: int) -> float:
        base = 0.5 * (2 ** attempt)
        return min(8.0, base)




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


def _normalize_role(value: str) -> str:
    lowered = value.strip().lower()
    return "".join(ch for ch in lowered if ch.isalnum())
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
    safe_name = requests.utils.quote(filename, safe="")
    return f"{url}?id={safe_name}@@@0"


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
