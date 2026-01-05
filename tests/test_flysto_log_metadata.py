from __future__ import annotations

import json

from src.core.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, text: str, status_code: int = 200) -> None:
    """Internal helper for init  ."""
        self.text = text
        self.status_code = status_code


class DummyFlyStoMetadata(FlyStoClient):
    def __init__(self, payload: dict) -> None:
    """Internal helper for init  ."""
        super().__init__(api_key="", base_url="https://example.test")
        self.payload = payload

    def _ensure_session(self, session):
    """Internal helper for ensure session."""
        return None

    def _request(self, session, method: str, url: str, **kwargs):
    """Internal helper for request."""
        return DummyResponse(text=json.dumps(self.payload))


def test_resolve_log_source_prefers_unknown_id_avionics():
"""Test resolve log source prefers unknown id avionics."""
    payload = {
        "items": [{"id": "log-1", "aircraft": 0}],
        "aircraft": [
            {
                "unknown-id": {
                    "avionics": {
                        "logFormatId": "UnknownGarmin",
                        "systemId": "system id: D-KBUH",
                    }
                }
            }
        ],
    }
    client = DummyFlyStoMetadata(payload)
    log_format, system_id = client.resolve_log_source_for_log_id("log-1")
    assert log_format == "UnknownGarmin"
    assert system_id == "system id: D-KBUH"


def test_resolve_log_source_uses_entry_avionics():
"""Test resolve log source uses entry avionics."""
    payload = {
        "items": [{"id": "log-1", "aircraft": 0}],
        "aircraft": [
            {"avionics": {"logFormatId": "GenericGpx", "systemId": "gpx"}}
        ],
    }
    client = DummyFlyStoMetadata(payload)
    log_format, system_id = client.resolve_log_source_for_log_id("log-1")
    assert log_format == "GenericGpx"
    assert system_id == "gpx"
