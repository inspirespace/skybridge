from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import requests

from src.models import FlightDetail


@dataclass(frozen=True)
class FlyStoClient:
    api_key: str
    base_url: str
    upload_url: str | None = None
    session_cookie: str | None = None
    include_metadata: bool = False

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> None:
        if dry_run:
            _validate_flight_for_upload(flight)
            return
        _validate_flight_for_upload(flight)
        if not self.upload_url:
            raise NotImplementedError("FlySto upload URL is not configured.")
        session = requests.Session()
        if self.session_cookie:
            session.cookies.set("USER_SESSION", self.session_cookie, domain="www.flysto.net", path="/")

        files = {"file": (Path(flight.file_path).name, open(flight.file_path, "rb"))}
        data = {}
        if self.include_metadata:
            data["metadata"] = json.dumps(_metadata_payload(flight))
        try:
            response = session.post(self.upload_url, files=files, data=data, timeout=60)
        finally:
            files["file"][1].close()

        if response.status_code >= 300:
            raise RuntimeError(
                f"FlySto upload failed: {response.status_code} {response.text[:300]}"
            )


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
