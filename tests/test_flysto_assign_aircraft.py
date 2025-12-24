from __future__ import annotations

from dataclasses import dataclass
import json

from src.flysto.client import FlyStoClient


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "ok"


class DummyFlySto(FlyStoClient):
    def __init__(self, metadata_response: dict | None = None):
        super().__init__(api_key="", base_url="https://example.test")
        self.request_calls: list[tuple[str, str, dict]] = []
        self.metadata_response = metadata_response or {}

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.request_calls.append((method.lower(), url, kwargs))
        if method.lower() == "get" and url.endswith("/api/log-metadata"):
            return DummyResponse(text=json.dumps(self.metadata_response))
        return DummyResponse()

    def resolve_log_for_file(self, filename: str, retries: int = 8, delay_seconds: float = 3.0):
        return "log-1", "sig", "GenericGpx"


def test_assign_aircraft_does_not_cache_unknown_group():
    client = DummyFlySto()

    client.assign_aircraft("tail-1", log_format_id="GenericGpx", system_id=None)
    client.assign_aircraft("tail-1", log_format_id="GenericGpx", system_id=None)

    assert len(client.request_calls) == 2
    assert client.assigned_avionics == set()


def test_assign_aircraft_caches_known_system_id():
    client = DummyFlySto()

    client.assign_aircraft("tail-1", log_format_id="GenericGpx", system_id="abc")
    client.assign_aircraft("tail-1", log_format_id="GenericGpx", system_id="abc")

    assert len(client.request_calls) == 1
    assert ("GenericGpx", "abc") in client.assigned_avionics


def test_assign_metadata_for_file_posts_remarks_and_tags():
    client = DummyFlySto(metadata_response={"tags": ["existing"], "remarks": "old"})

    client.assign_metadata_for_file("A1.gpx", remarks="New remarks", tags=["cloudahoy:A1", "training"])

    post_calls = [call for call in client.request_calls if call[0] == "post"]
    assert post_calls
    _method, url, kwargs = post_calls[-1]
    assert url.endswith("/api/log-metadata")
    payload = kwargs.get("json", {})
    assert payload.get("logIdString") == "log-1"
    assert payload.get("remarks") == "New remarks"
    assert "cloudahoy:A1" in payload.get("tags", [])
    assert "training" in payload.get("tags", [])
    assert "existing" in payload.get("tags", [])
