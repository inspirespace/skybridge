from __future__ import annotations

from dataclasses import dataclass
import json

from src.core.flysto.client import FlyStoClient


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "ok"


class DummyFlySto(FlyStoClient):
    def __init__(self):
        super().__init__(api_key="", base_url="https://example.test")
        self.request_calls: list[tuple[str, str, dict]] = []

    def _ensure_session(self, session):
        return None

    def _request(self, session, method: str, url: str, **kwargs):
        self.request_calls.append((method.lower(), url, kwargs))
        return DummyResponse()

    def resolve_log_for_file(
        self,
        filename: str,
        retries: int = 8,
        delay_seconds: float = 3.0,
        logs_limit: int = 250,
    ):
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


def test_assign_metadata_for_file_puts_remarks_and_tags():
    client = DummyFlySto()

    client.assign_metadata_for_file("A1.gpx", remarks="New remarks", tags=["cloudahoy", "cloudahoy:2025-03-20T15:37Z"])

    post_calls = [call for call in client.request_calls if call[0] == "post"]
    assert not post_calls
    put_calls = [call for call in client.request_calls if call[0] == "put"]
    assert put_calls
    _method, url, kwargs = put_calls[-1]
    assert url.endswith("/api/log-annotations/log-1")
    payload = kwargs.get("json", {})
    assert payload.get("logIdString") == "log-1"
    assert payload.get("remarks") == "New remarks"
    assert "cloudahoy" in payload.get("tags", [])
    assert "cloudahoy:2025-03-20T15:37Z" in payload.get("tags", [])


def test_ensure_crew_members_tolerates_existing():
    class DummyFlyStoCrew(FlyStoClient):
        def __init__(self):
            super().__init__(api_key="", base_url="https://example.test")
            self.failed_create = False
            self.requested_names: list[str] = []

        def _ensure_session(self, session):
            return None

        def _request(self, session, method: str, url: str, **kwargs):
            if method.lower() == "post" and url.endswith("/api/new-crew"):
                name = kwargs.get("json", {}).get("name")
                if name:
                    self.requested_names.append(name)
                self.failed_create = True
                return DummyResponse(status_code=409, text="exists")
            return DummyResponse()

        def _list_crew(self):
            if self.failed_create:
                return [{"name": "Alex"}]
            return []

    client = DummyFlyStoCrew()
    client._ensure_crew_members(["Alex"])
    assert client.requested_names == ["Alex"]


def test_resolve_log_cached_across_assignments():
    class DummyFlyStoCached(FlyStoClient):
        def __init__(self):
            super().__init__(api_key="", base_url="https://example.test")
            self.resolve_calls = 0
            self.assigned: list[tuple[list[str], list[str], list[str]]] = []

        def _ensure_session(self, session):
            return None

        def _resolve_log_for_file_uncached(
            self,
            filename: str,
            retries: int = 8,
            delay_seconds: float = 3.0,
            logs_limit: int = 250,
        ):
            self.resolve_calls += 1
            return "log-1", "sig", "GenericGpx"

        def _ensure_crew_members(self, names):
            return None

        def _list_crew_roles(self):
            return [{"id": "role-1", "name": "Pilot"}]

        def assign_aircraft(self, aircraft_id: str, log_format_id: str = "GenericGpx", system_id: str | None = None):
            return None

        def _assign_crew(self, log_ids: list[str], names: list[str], roles: list[str]) -> None:
            self.assigned.append((log_ids, names, roles))

    client = DummyFlyStoCached()
    client.assign_aircraft_for_file("A1.gpx", "tail-1")
    client.assign_crew_for_file(
        "A1.gpx",
        [{"name": "Alex", "role": "Pilot", "is_pic": True}],
    )

    assert client.resolve_calls == 1
    assert client.assigned == [(["log-1"], ["Alex"], ["role-1"])]


def test_assign_crew_for_log_id_skips_resolution():
    class DummyFlyStoNoResolve(FlyStoClient):
        def __init__(self):
            super().__init__(api_key="", base_url="https://example.test")
            self.resolve_calls = 0
            self.assigned: list[tuple[list[str], list[str], list[str]]] = []

        def _ensure_session(self, session):
            return None

        def _resolve_log_for_file_uncached(
            self,
            filename: str,
            retries: int = 8,
            delay_seconds: float = 3.0,
            logs_limit: int = 250,
        ):
            self.resolve_calls += 1
            return "log-1", "sig", "GenericGpx"

        def _ensure_crew_members(self, names):
            return None

        def _list_crew_roles(self):
            return [{"id": "role-1", "name": "Pilot"}]

        def _assign_crew(self, log_ids: list[str], names: list[str], roles: list[str]) -> None:
            self.assigned.append((log_ids, names, roles))

    client = DummyFlyStoNoResolve()
    client.assign_crew_for_log_id(
        "log-9",
        [{"name": "Alex", "role": "Pilot", "is_pic": True}],
    )

    assert client.resolve_calls == 0
    assert client.assigned == [(["log-9"], ["Alex"], ["role-1"])]


def test_assign_crew_payload_matches_ui_format():
    class DummyFlyStoPayload(FlyStoClient):
        def __init__(self):
            super().__init__(api_key="", base_url="https://example.test")
            self.request_calls: list[tuple[str, str, dict]] = []

        def _ensure_session(self, session):
            return None

        def _request(self, session, method: str, url: str, **kwargs):
            self.request_calls.append((method.lower(), url, kwargs))
            return DummyResponse()

        def _ensure_crew_members(self, names):
            return None

        def _list_crew_roles(self):
            return [{"id": "-6", "name": "Student"}]

    client = DummyFlyStoPayload()
    client.assign_crew_for_log_id(
        "log-1",
        [{"name": "Alex", "role": "Student", "is_pic": False}],
    )

    method, url, kwargs = client.request_calls[-1]
    assert method == "post"
    assert url.endswith("/api/assign-crew")
    assert kwargs.get("headers", {}).get("content-type") == "text/plain;charset=UTF-8"
    payload = json.loads(kwargs.get("data", "{}"))
    assert payload["logIds"] == ["log-1"]
    assert payload["names"] == ["Alex"]
    assert payload["roles"] == [-6]


def test_list_crew_falls_back_to_all():
    class DummyFlyStoCrewFallback(FlyStoClient):
        def __init__(self):
            super().__init__(api_key="", base_url="https://example.test")
            self.calls: list[tuple[str, str, dict]] = []

        def _ensure_session(self, session):
            return None

        def _request(self, session, method: str, url: str, **kwargs):
            self.calls.append((method.lower(), url, kwargs))
            if url.endswith("/api/user-crew"):
                return DummyResponse(text="[]")
            if "/api/crew" in url:
                return DummyResponse(text='[{"id":1,"name":"Alex"}]')
            return DummyResponse()

    client = DummyFlyStoCrewFallback()
    crew = client._list_crew()
    assert crew == [{"id": 1, "name": "Alex"}]
