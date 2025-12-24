from __future__ import annotations

from dataclasses import dataclass

from src.flysto.client import FlyStoClient


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "ok"


class DummyFlySto(FlyStoClient):
    def __init__(self):
        super().__init__(api_key="", base_url="https://example.test")
        self.request_calls: list[tuple[str, str]] = []

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.request_calls.append((method.lower(), url))
        return DummyResponse()


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
