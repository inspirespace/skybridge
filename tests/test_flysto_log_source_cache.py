from __future__ import annotations

import json

from src.core.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
        self.text = text
        self.status_code = status_code


class DummyFlyStoCached(FlyStoClient):
    def __init__(self, payload: dict) -> None:
        super().__init__(api_key="", base_url="https://example.test")
        self.payload = payload
        self.request_count = 0

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.request_count += 1
        return DummyResponse(text=json.dumps(self.payload))


def test_resolve_log_source_is_cached():
    payload = {
        "items": [{"id": "log-1", "aircraft": 0}],
        "aircraft": [{"avionics": {"logFormatId": "GenericGpx", "systemId": "gpx"}}],
    }
    client = DummyFlyStoCached(payload)
    first = client.resolve_log_source_for_log_id("log-1")
    second = client.resolve_log_source_for_log_id("log-1")
    assert first == ("GenericGpx", "gpx")
    assert second == ("GenericGpx", "gpx")
    assert client.request_count == 1
