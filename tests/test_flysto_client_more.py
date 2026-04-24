"""More FlySto client tests covering crew/roles/metadata and resolve paths."""
from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from src.core.flysto.client import FlyStoClient


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "{}"


class DummyFlySto(FlyStoClient):
    def __init__(self):
        super().__init__(api_key="", base_url="https://example.test")
        self.request_calls: list[tuple[str, str, dict]] = []
        self.responses: list[DummyResponse] = []

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.request_calls.append((method.lower(), url, kwargs))
        if self.responses:
            return self.responses.pop(0)
        return DummyResponse()


def test_list_crew_roles_prefers_pic():
    client = DummyFlySto()
    client.responses = [
        DummyResponse(text=json.dumps([{"id": "1", "name": "Pilot in command"}]))
    ]
    role_id = client._default_role_id()
    assert role_id == "1"


def test_resolve_role_id_fallback_to_copilot():
    client = DummyFlySto()
    client.responses = [
        DummyResponse(text=json.dumps([{"id": "3", "name": "Copilot"}]))
    ]
    role_id = client._resolve_role_id("pilot", is_pic=False)
    assert role_id == "3"


def test_assign_metadata_for_log_id_skips_empty():
    client = DummyFlySto()
    client.assign_metadata_for_log_id(None, remarks=None, tags=None)
    assert client.request_calls == []


def test_update_remarks_error():
    client = DummyFlySto()
    client.responses = [DummyResponse(status_code=500, text="boom")]
    with pytest.raises(RuntimeError):
        client._update_remarks("log-1", "bad")


def test_assign_tags_error():
    client = DummyFlySto()
    client.responses = [DummyResponse(status_code=500, text="boom")]
    with pytest.raises(RuntimeError):
        client._assign_tags(["log-1"], add=["t1"])


def test_assign_crew_validation():
    client = DummyFlySto()
    client._assign_crew([], [], [])
    with pytest.raises(ValueError):
        client._assign_crew(["log"], ["name", "two"], ["1"])


def test_assign_crew_logs_404_without_raising():
    client = DummyFlySto()
    client.responses = [DummyResponse(status_code=404, text="missing")]
    client._assign_crew(["log"], ["name"], ["1"])
    assert client.request_calls


def test_resolve_log_for_file_uncached_hits_update_true():
    client = DummyFlySto()
    client.responses = [
        DummyResponse(text=json.dumps(["log-1"])),
        DummyResponse(text=json.dumps({"items": []})),
        DummyResponse(text=json.dumps({"items": []})),
    ]
    log_id, signature, log_format = client._resolve_log_for_file_uncached(
        "flight.gpx",
        retries=1,
        delay_seconds=0,
        logs_limit=1,
    )
    assert (log_id, signature, log_format) == (None, None, None)


def test_resolve_log_source_selects_unknown_avionics():
    payload = {
        "items": [{"id": "log-1", "aircraft": 0}],
        "aircraft": [
            {"unknown-id": {"avionics": {"logFormat": "Gpx", "systemId": "sys"}}}
        ],
    }
    client = DummyFlySto()
    client.responses = [DummyResponse(text=json.dumps(payload))]
    fmt, sys_id = client.resolve_log_source_for_log_id("log-1")
    assert fmt == "Gpx"
    assert sys_id == "sys"


def test_ensure_aircraft_missing_tail_returns_none():
    client = DummyFlySto()
    assert client.ensure_aircraft(None) is None
