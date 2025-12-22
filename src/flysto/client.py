from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re

import requests

from src.models import FlightDetail


@dataclass(frozen=True)
class FlyStoClient:
    api_key: str
    base_url: str
    upload_url: str | None = None
    session_cookie: str | None = None
    include_metadata: bool = False
    api_version: str | None = None
    email: str | None = None
    password: str | None = None

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
        payload = file_path.read_bytes()
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

    def _ensure_session(self, session: requests.Session) -> None:
        if self.session_cookie:
            session.cookies.set(
                "USER_SESSION",
                self.session_cookie,
                domain="www.flysto.net",
                path="/",
            )
            return
        if self.email and self.password:
            _api_login(session, self.base_url, self.email, self.password, self.api_version)
            return
        raise NotImplementedError("FlySto API auth not configured.")


def _validate_flight_for_upload(flight: FlightDetail) -> None:
    if not flight.file_path:
        raise RuntimeError("Flight export file is required for FlySto upload.")
    path = Path(flight.file_path)
    if not path.exists():
        raise RuntimeError("Flight export file missing on disk.")


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
    try:
        login = requests.get(base_url.rstrip("/") + "/login", timeout=30)
        login.raise_for_status()
        match = re.search(r"/static/(flysto\\.[^\\\"']+\\.js)", login.text)
        if not match:
            return None
        bundle_url = base_url.rstrip("/") + "/static/" + match.group(1)
        bundle = requests.get(bundle_url, timeout=30)
        bundle.raise_for_status()
        match = re.search(r"x-version\"\\s*[:,]\\s*\"?(\\d+)\"?", bundle.text)
        if match:
            return match.group(1)
    except Exception:
        return None
    return None
