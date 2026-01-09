"""Extra FlySto client coverage tests."""
from __future__ import annotations

import json

import pytest

from src.core.flysto.client import FlyStoClient


class DummyResponse:
    def __init__(self, status_code: int = 200, text: str = "{}") -> None:
        self.status_code = status_code
        self.text = text


class DummyFlySto(FlyStoClient):
    def __init__(self):
        super().__init__(api_key="", base_url="https://example.test")
        self.responses: list[DummyResponse] = []
        self.requests: list[tuple[str, str]] = []
        self.aircraft: list[dict] = []
        self._ensure_called = 0

    def _ensure_session(self, _session):
        self._ensure_called += 1

    def _request(self, _session, method: str, url: str, **kwargs):
        self.requests.append((method, url))
        if self.responses:
            return self.responses.pop(0)
        return DummyResponse()

    def _list_aircraft(self, _session):
        return self.aircraft


def test_ensure_aircraft_returns_existing():
    client = DummyFlySto()
    client.aircraft = [{"tail-number": "N123", "id": "air-1"}]
    aircraft = client.ensure_aircraft("N123")
    assert aircraft["id"] == "air-1"


def test_ensure_aircraft_missing_model_raises(monkeypatch: pytest.MonkeyPatch):
    client = DummyFlySto()
    monkeypatch.setattr(client, "_match_model_id", lambda _aircraft_type: None)
    with pytest.raises(RuntimeError):
        client.ensure_aircraft("N123")


def test_ensure_aircraft_fallback_to_other_model():
    client = DummyFlySto()
    client.aircraft_profiles_cache = [
        {"modelId": "C172", "modelName": "C172"}
    ]
    client.responses = [DummyResponse(status_code=500, text="fail"), DummyResponse(status_code=200, text="ok")]

    calls = {"count": 0}

    def list_after(_session):
        if calls["count"] == 0:
            calls["count"] += 1
            return []
        return [{"tail-number": "N999", "id": "air-9"}]

    client._list_aircraft = list_after
    aircraft = client.ensure_aircraft("N999", aircraft_type="C172")
    assert aircraft["id"] == "air-9"


def test_assign_aircraft_skips_duplicate_system_id():
    client = DummyFlySto()
    client.assigned_avionics = set()
    client.responses = [DummyResponse(status_code=200, text="ok")]

    client.assign_aircraft("air-1", log_format_id="GenericGpx", system_id="sys-1")
    client.assign_aircraft("air-1", log_format_id="GenericGpx", system_id="sys-1")
    assert len(client.requests) == 1


def test_resolve_log_source_for_log_id_parses_metadata():
    client = DummyFlySto()
    payload = {
        "items": [{"id": "log-1", "aircraft": 0}],
        "aircraft": [
            {
                "avionics": {"logFormatId": "UnknownGarmin", "systemId": "sys-1"}
            }
        ],
    }
    client.responses = [DummyResponse(status_code=200, text=json.dumps(payload))]
    log_format, system_id = client.resolve_log_source_for_log_id("log-1")
    assert log_format == "UnknownGarmin"
    assert system_id == "sys-1"


def test_list_crew_fallback_path():
    client = DummyFlySto()
    client.responses = [
        DummyResponse(status_code=200, text=json.dumps([])),
        DummyResponse(status_code=200, text=json.dumps([{"name": "Alex"}])),
    ]
    crew = client._list_crew()
    assert crew[0]["name"] == "Alex"
