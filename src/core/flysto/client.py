"""src/core/flysto/client.py module."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
import tempfile
import time
from typing import Any
import zipfile
from urllib.parse import urljoin, urlparse

import requests

from src.core.models import FlightDetail


@dataclass(frozen=True)
class UploadResult:
    signature: str | None
    log_id: str | None
    log_format: str | None
    signature_hash: str | None = None


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
    min_request_interval: float = 0.01
    max_request_retries: int = 2
    _last_request_at: float | None = None
    log_cache: dict[str, tuple[str | None, str | None, str | None]] = field(
        default_factory=dict
    )
    upload_cache: dict[str, UploadResult] = field(default_factory=dict)
    log_source_cache: dict[str, tuple[str | None, str | None]] = field(default_factory=dict)

    def prepare(self) -> bool:
        """Handle prepare."""
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

    def trim_caches(self, *, keep: int = 8) -> None:
        """Cap per-file caches so long imports don't grow unbounded.

        Each entry is only needed for the current flight's report item; once
        that item is persisted, older entries are dead weight against the
        256 MiB worker budget.
        """
        for cache in (self.log_cache, self.upload_cache, self.log_source_cache):
            while len(cache) > keep:
                oldest = next(iter(cache))
                cache.pop(oldest, None)

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> "UploadResult | None":
        """Handle upload flight."""
        if dry_run:
            _validate_flight_for_upload(flight)
            return None
        _validate_flight_for_upload(flight)
        session = requests.Session()
        self._ensure_session(session)
        if not self.api_version:
            self.api_version = _infer_api_version(self.base_url)

        file_path = Path(flight.file_path)
        body_path, cleanup = _build_upload_payload(file_path)
        headers = {"content-type": "application/zip"}
        if self.api_version:
            headers["x-version"] = self.api_version
        try:
            with body_path.open("rb") as body:
                response = self._request(
                    session,
                    "post",
                    _upload_url(self.upload_url, self.base_url, file_path.name),
                    data=body,
                    headers=headers,
                    timeout=120,
                )
        finally:
            if cleanup:
                try:
                    body_path.unlink()
                except OSError:
                    pass

        if response.status_code >= 300:
            error_message = f"FlySto upload failed: {response.status_code} {response.text[:300]}"
            if _is_duplicate_upload_error(response.status_code, response.text):
                raise RuntimeError(f"duplicate upload: {error_message}")
            raise RuntimeError(error_message)
        result = _parse_upload_response(response.text, file_path.name)
        if result:
            self.upload_cache[file_path.name] = result
        return result


    def ensure_aircraft(self, tail_number: str | None, aircraft_type: str | None = None) -> dict[str, Any] | None:
        """Handle ensure aircraft."""
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
        """Internal helper for find aircraft by tail."""
        aircraft = self._list_aircraft(session)
        for entry in aircraft:
            if entry.get("tail-number") == tail_number or entry.get("tailNumber") == tail_number:
                return entry
        return None

    def _list_aircraft(self, session: requests.Session) -> list[dict[str, Any]]:
        """Internal helper for list aircraft."""
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
        """Internal helper for match model id."""
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
        """Internal helper for list aircraft profiles."""
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
        """Handle assign aircraft."""
        if not aircraft_id:
            return
        key = (log_format_id, system_id)
        if self.assigned_avionics is None:
            self.assigned_avionics = set()
        if system_id is not None and key in self.assigned_avionics:
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
        if system_id is not None:
            self.assigned_avionics.add(key)


    def resolve_log_for_file(
        self,
        filename: str,
        retries: int = 8,
        delay_seconds: float = 3.0,
        logs_limit: int = 250,
    ) -> tuple[str | None, str | None, str | None]:
        """Handle resolve log for file."""
        cached = self.log_cache.get(filename)
        if cached is not None:
            return cached
        log_id, signature, log_format = self._resolve_log_for_file_uncached(
            filename,
            retries=retries,
            delay_seconds=delay_seconds,
            logs_limit=logs_limit,
        )
        if log_id or signature or log_format:
            self.log_cache[filename] = (log_id, signature, log_format)
        return log_id, signature, log_format

    def _resolve_log_for_file_uncached(
        self,
        filename: str,
        retries: int = 8,
        delay_seconds: float = 3.0,
        logs_limit: int = 250,
    ) -> tuple[str | None, str | None, str | None]:
        """Internal helper for resolve log for file uncached."""
        session = requests.Session()
        self._ensure_session(session)
        keys = "57,tf,ec,hq,86,b2,lb,8q,p2,85,bl,hk,4n,ee,yu,1y,t3,ng,ho,hq,x9,g3,6n,hq,0s,83,6h,am"
        for log_type in ("flight", "all"):
            log_ids: list[str] = []
            for attempt in range(retries):
                params = {"type": log_type, "logs": logs_limit, "order": "descending"}
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
                    break
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
        """Handle assign aircraft for file."""
        log_id, signature, resolved_format = self.resolve_log_for_file(filename)
        self.assign_aircraft_for_signature(
            aircraft_id=aircraft_id,
            signature=signature,
            log_format_id=log_format_id,
            resolved_format=resolved_format,
        )

    def assign_aircraft_for_signature(
        self,
        aircraft_id: str,
        signature: str | None,
        log_format_id: str = "GenericGpx",
        resolved_format: str | None = None,
    ) -> None:
        """Handle assign aircraft for signature."""
        if not signature:
            return
        effective_format = resolved_format or log_format_id
        self.assign_aircraft(aircraft_id, log_format_id=effective_format, system_id=signature)

    def resolve_log_source_for_log_id(
        self,
        log_id: str,
        include_annotations: bool = True,
    ) -> tuple[str | None, str | None]:
        """Handle resolve log source for log id."""
        cached = self.log_source_cache.get(log_id)
        if cached is not None:
            return cached
        session = requests.Session()
        self._ensure_session(session)
        params = {"logIdString": log_id}
        if include_annotations:
            params["annotations"] = "true"
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/log-metadata",
            params=params,
            timeout=60,
        )
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                decoded = json.loads(decoded)
            except json.JSONDecodeError:
                decoded = None
        if not isinstance(decoded, dict):
            return None, None
        items = decoded.get("items", [])
        aircraft_list = decoded.get("aircraft", [])
        entry = None
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and item.get("id") == log_id:
                    idx = item.get("aircraft")
                    if isinstance(idx, int) and 0 <= idx < len(aircraft_list):
                        entry = aircraft_list[idx]
                    break
        if entry is None and aircraft_list:
            entry = aircraft_list[0]
        log_format_id = None
        system_id = None
        if isinstance(entry, dict):
            unknown = (
                entry.get("unknown-id")
                or entry.get("unknown_id")
                or entry.get("unknownId")
            )
            avionics = None
            if isinstance(unknown, dict):
                avionics = unknown.get("avionics")
            if not avionics and isinstance(entry.get("avionics"), dict):
                avionics = entry.get("avionics")
            if isinstance(avionics, dict):
                log_format_id = (
                    avionics.get("logFormatId")
                    or avionics.get("logFormat")
                    or avionics.get("log_format_id")
                )
                system_id = avionics.get("systemId") or avionics.get("system_id")
        self.log_source_cache[log_id] = (log_format_id, system_id)
        return log_format_id, system_id

    def assign_crew_for_file(self, filename: str, crew: list[dict[str, Any]]) -> None:
        """Handle assign crew for file."""
        if not crew:
            return
        log_id, _signature, _format = self.resolve_log_for_file(filename)
        self.assign_crew_for_log_id(log_id, crew)

    def assign_crew_for_log_id(self, log_id: str | None, crew: list[dict[str, Any]]) -> None:
        """Handle assign crew for log id."""
        if not log_id:
            return
        self.assign_crew_for_log_ids([log_id], crew)

    def assign_crew_for_log_ids(
        self, log_ids: list[str], crew: list[dict[str, Any]]
    ) -> None:
        """Assign the same crew to multiple logs in a single POST.

        ``/api/assign-crew`` accepts a list of ``logIds`` alongside the names
        and roles, so when many flights share identical crew (e.g. a pilot's
        solo flights, a student's lessons with one instructor) we can fold
        N assignments into one round-trip. Empty/invalid log_ids are dropped.
        """
        filtered_ids = [log_id for log_id in log_ids if log_id]
        if not filtered_ids:
            return
        names: list[str] = []
        roles: list[int | str] = []
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
            roles.append(_coerce_role_id(role_id))
        if not names or not roles:
            return
        self._assign_crew(filtered_ids, names, roles)

    def assign_metadata_for_file(
        self,
        filename: str,
        remarks: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Handle assign metadata for file."""
        if not remarks and not tags:
            return
        log_id, _signature, _format = self.resolve_log_for_file(filename)
        self.assign_metadata_for_log_id(log_id, remarks=remarks, tags=tags)

    def assign_metadata_for_log_id(
        self,
        log_id: str | None,
        remarks: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        """Handle assign metadata for log id.

        FlySto split this into two endpoints: tags go through ``POST /api/tags``
        (batch add/remove), and remarks go through
        ``PUT /api/log-annotations/{id}?annotations=remarks``.
        """
        if not log_id:
            return
        merged_tags = _normalize_tag_list(tags)
        if merged_tags:
            self._assign_tags([log_id], add=merged_tags, remove=[])
        if remarks:
            self._update_remarks(log_id, remarks)

    def fetch_log_metadata(
        self,
        log_id: str,
        annotations: str = "crew,tags,remarks",
    ) -> dict[str, Any] | None:
        """Handle fetch log metadata."""
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/log-metadata",
            params={"log": log_id, "annotations": annotations},
            timeout=60,
        )
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                decoded = json.loads(decoded)
            except json.JSONDecodeError:
                return None
        if isinstance(decoded, dict):
            return decoded
        return None

    def _update_remarks(self, log_id: str, remarks: str) -> None:
        """Set remarks on a log via ``PUT /api/log-annotations/{id}?annotations=remarks``."""
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "put",
            self.base_url.rstrip("/") + f"/api/log-annotations/{log_id}",
            params={"annotations": "remarks"},
            data=json.dumps({"remarks": remarks}),
            headers={"content-type": "text/plain;charset=UTF-8"},
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto log-annotations failed: {response.status_code} {response.text[:200]}"
            )

    def _assign_tags(
        self,
        log_ids: list[str],
        add: list[str],
        remove: list[str] | None = None,
    ) -> None:
        """Add/remove tags on logs via ``POST /api/tags``.

        Batch endpoint — one call can tag many logs at once.
        """
        filtered = [log_id for log_id in log_ids if log_id]
        add_list = [tag for tag in (add or []) if tag]
        remove_list = [tag for tag in (remove or []) if tag]
        if not filtered or (not add_list and not remove_list):
            return
        session = requests.Session()
        self._ensure_session(session)
        payload = {"logIds": filtered, "add": add_list, "remove": remove_list}
        response = self._request(
            session,
            "post",
            self.base_url.rstrip("/") + "/api/tags",
            data=json.dumps(payload),
            headers={"content-type": "text/plain;charset=UTF-8"},
            timeout=60,
        )
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto log-annotations failed: {response.status_code} {response.text[:200]}"
            )

    def _assign_crew(
        self,
        log_ids: list[str],
        names: list[str],
        roles: list[int | str],
    ) -> None:
        """Internal helper for assign crew.

        Calls ``POST /api/assign-crew-role`` with
        ``{logIds, assignments: [{role, names}]}`` — names are grouped by role.
        """
        if not log_ids or not names or not roles:
            return
        if len(names) != len(roles):
            raise ValueError("FlySto crew assignment requires matching names and roles length.")
        assignments_by_role: dict[int | str, list[str]] = {}
        for name, role in zip(names, roles):
            assignments_by_role.setdefault(role, []).append(name)
        assignments = [
            {"role": role, "names": role_names}
            for role, role_names in assignments_by_role.items()
        ]
        session = requests.Session()
        self._ensure_session(session)
        payload = {"logIds": log_ids, "assignments": assignments}
        response = self._request(
            session,
            "post",
            self.base_url.rstrip("/") + "/api/assign-crew-role",
            data=json.dumps(payload),
            headers={"content-type": "text/plain;charset=UTF-8"},
            timeout=60,
        )
        if response.status_code == 404:
            import sys
            print(
                f"FlySto assign-crew-role 404 for logIds={log_ids}: {response.text[:200]}",
                file=sys.stderr,
            )
            return
        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto assign-crew failed: {response.status_code} {response.text[:200]}"
            )

    def _ensure_crew_members(self, names: list[str]) -> None:
        """Internal helper for ensure crew members."""
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
                # If the crew already exists, tolerate the error and continue.
                self.crew_cache = None
                existing_now = {
                    self._crew_name(entry)
                    for entry in self._list_crew()
                    if self._crew_name(entry)
                }
                if name in existing_now:
                    continue
                raise RuntimeError(
                    f"FlySto create-crew failed: {response.status_code} {response.text[:200]}"
                )
            existing.add(name)
        self.crew_cache = None

    def _list_crew(self) -> list[dict[str, Any]]:
        """Internal helper for list crew."""
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
        if not data:
            response = self._request(
                session,
                "get",
                self.base_url.rstrip("/") + "/api/crew",
                params={"type": "all"},
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
        """Internal helper for crew name."""
        for key in ("name", "fullName", "crewName"):
            value = entry.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def _list_crew_roles(self) -> list[dict[str, Any]]:
        """Internal helper for list crew roles."""
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
        """Internal helper for default role id."""
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
        """Internal helper for resolve role id."""
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
                candidates.extend(["Copilot", "Co-pilot", "Co pilot"])
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
        """Internal helper for role id name."""
        role_id = role.get("id") or role.get("crewRoleId") or role.get("roleId")
        name = role.get("name") or role.get("crewRoleName") or role.get("roleName")
        role_id = str(role_id) if role_id is not None else None
        if isinstance(name, str):
            name = name.strip()
        return role_id, name if isinstance(name, str) else None

    def log_files_to_process(self) -> int | None:
        """Handle log files to process."""
        session = requests.Session()
        self._ensure_session(session)
        response = self._request(
            session,
            "get",
            self.base_url.rstrip("/") + "/api/log-files-to-process",
            timeout=60,
        )
        decoded = _decode_flysto_payload(response.text)
        if isinstance(decoded, str):
            try:
                decoded = json.loads(decoded)
            except json.JSONDecodeError:
                return None
        if isinstance(decoded, dict):
            count = decoded.get("nFiles")
            if isinstance(count, int):
                return count
        return None

    def _ensure_session(self, session: requests.Session) -> None:
        """Internal helper for ensure session."""
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
        """Internal helper for request."""
        method = method.lower()
        if self.api_version:
            headers = dict(kwargs.get("headers") or {})
            if not any(key.lower() == "x-version" for key in headers):
                headers["x-version"] = self.api_version
            kwargs["headers"] = headers
        body = kwargs.get("data")
        seekable = body is not None and hasattr(body, "seek") and hasattr(body, "tell")
        body_start = None
        if seekable:
            try:
                body_start = body.tell()
            except Exception:
                seekable = False
        last_error = None
        for attempt in range(self.max_request_retries):
            if seekable and attempt > 0:
                try:
                    body.seek(body_start)
                except Exception:
                    pass
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
        """Internal helper for respect rate limit."""
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
        """Internal helper for retry delay."""
        base = 0.5 * (2 ** attempt)
        return min(8.0, base)


def _coerce_role_id(value: str) -> int | str:
    """Internal helper for coerce role id."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return value




def _decode_flysto_payload(text: str) -> Any:
    """Internal helper for decode flysto payload."""
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
    """Internal helper for swap chars."""
    chars: list[str] = []
    for ch in value:
        code = ord(ch)
        if 32 <= code <= 127:
            chars.append(chr((127 - code) + 32))
        else:
            chars.append(ch)
    return "".join(chars)


def _normalize_role(value: str) -> str:
    """Internal helper for normalize role."""
    lowered = value.strip().lower()
    return "".join(ch for ch in lowered if ch.isalnum())


def _normalize_tag_list(value: object) -> list[str]:
    """Internal helper for normalize tag list."""
    if value is None:
        return []
    if isinstance(value, list):
        raw = [entry for entry in value if isinstance(entry, str)]
    elif isinstance(value, str):
        raw = [entry.strip() for entry in value.split(",")]
    else:
        return []
    tags = [entry.strip() for entry in raw if entry and entry.strip()]
    return tags


def _validate_flight_for_upload(flight: FlightDetail) -> None:
    """Internal helper for validate flight for upload."""
    if not flight.file_path:
        raise RuntimeError("Flight export file is required for FlySto upload.")
    path = Path(flight.file_path)
    if not path.exists():
        raise RuntimeError("Flight export file missing on disk.")




def _build_upload_payload(path: Path) -> tuple[Path, bool]:
    """Return a path to a zip body plus whether the caller should delete it.

    The zip is built by streaming the source file through ``ZipFile.write`` so
    the upload never holds the full file (or the compressed copy) in memory.
    """
    if path.suffix.lower() == ".zip":
        return path, False
    tmp_fd, tmp_name = tempfile.mkstemp(suffix=".zip")
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(path, arcname=path.name)
    except Exception:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise
    return tmp_path, True


def _parse_upload_response(text: str, filename: str) -> UploadResult | None:
    """Internal helper for parse upload response.

    FlySto's upload response only returns ``{"signature": "<uuid>.<ext>/<hash>/<numeric>"}``.
    The trailing numeric is a legacy internal ID that the newer annotation
    endpoints (``assign-crew-role``, ``tags``, ``log-annotations``) no longer
    accept — they want the short slug like ``pawxhmxw`` which FlySto exposes
    via ``/api/log-summary``. So we deliberately drop the numeric here and
    force callers to resolve the slug via ``resolve_log_for_file``.
    """
    raw = text.strip()
    if not raw:
        return None
    data: Any = None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        decoded = _decode_flysto_payload(raw)
        if isinstance(decoded, str):
            try:
                data = json.loads(decoded)
            except json.JSONDecodeError:
                data = decoded
        else:
            data = decoded

    if isinstance(data, dict):
        sig_value = data.get("signature") or data.get("sig") or data.get("logSignature")
        log_format = data.get("format") or data.get("logFormatId") or data.get("logFormat")
    else:
        sig_value = data if isinstance(data, str) else None
        log_format = None

    if not sig_value:
        match = re.search(r"\"signature\"\\s*:\\s*\"([^\"]+)\"", raw)
        if match:
            sig_value = match.group(1)

    signature = None
    signature_hash = None
    if isinstance(sig_value, str) and sig_value:
        signature, _legacy_numeric_id, signature_hash = _parse_signature_field(sig_value, filename)

    if not signature and not log_format:
        return None
    return UploadResult(
        signature=signature,
        log_id=None,
        log_format=log_format,
        signature_hash=signature_hash,
    )


def _is_duplicate_upload_error(status_code: int, payload: str | None) -> bool:
    """Return True when upload errors indicate a duplicate upload."""
    if status_code == 409:
        return True
    if not payload:
        return False
    normalized = payload.lower()
    duplicate_markers = ("already", "duplicate", "exists", "conflict")
    return any(marker in normalized for marker in duplicate_markers)


def _parse_signature_field(value: str, filename: str) -> tuple[str | None, str | None, str | None]:
    """Internal helper for parse signature field."""
    cleaned = value.strip()
    if not cleaned:
        return None, None, None
    if "/" not in cleaned:
        return cleaned, None, None
    parts = [part for part in cleaned.split("/") if part]
    if len(parts) >= 3:
        # expected: <filename>/<signature>/<log_id>
        return cleaned, parts[-1], parts[-2]
    if len(parts) == 2:
        return cleaned, None, parts[-1]
    return cleaned, None, None
def _metadata_payload(flight: FlightDetail) -> dict:
    """Internal helper for metadata payload."""
    payload = flight.raw_payload.get("flt", {}).get("Meta", {})
    if not isinstance(payload, dict):
        return {}
    return payload


def _upload_url(upload_url: str | None, base_url: str, filename: str) -> str:
    """Internal helper for upload url."""
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
    """Internal helper for api login."""
    url = base_url.rstrip("/") + "/api/login"
    headers = {"content-type": "text/plain;charset=UTF-8"}
    if api_version:
        headers["x-version"] = api_version
    payload = json.dumps({"email": email, "password": password})
    response = session.post(url, data=payload, headers=headers, timeout=60)
    if response.status_code >= 300:
        raise RuntimeError(f"FlySto API login failed: {response.status_code}")


def _infer_api_version(base_url: str) -> str | None:
    """Internal helper for infer api version."""
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
            match = re.search(r"/static/(flysto\.[^\"']+\.js)", login.text)
            if not match:
                continue
            base_root = "{uri.scheme}://{uri.netloc}/".format(
                uri=urlparse(login_url)
            )
            bundle_url = urljoin(base_root, f"static/{match.group(1)}")
            bundle = requests.get(bundle_url, timeout=30)
            bundle.raise_for_status()
            match = re.search(r'x-version"\s*[:,]\s*"?(\d+)"?', bundle.text)
            if not match:
                match = re.search(r'X-Version`\s*,\s*`(\d+)`', bundle.text)
            if match:
                return match.group(1)
        except Exception:
            continue
    return None
