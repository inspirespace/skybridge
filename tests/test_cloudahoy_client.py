"""tests/test_cloudahoy_client.py module."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from src.core.cloudahoy.client import (
    CloudAhoyClient,
    _api_base,
    _build_auth_payload,
    _csv_suffix,
    _extract_cookie,
    _extract_fdid_from_payload,
    _extract_kml,
    _extract_last_token,
    _extract_metadata,
    _from_unix,
    _is_tail_candidate,
    _login,
    _matches_tail_pattern,
    _normalize_tail_number,
)


@dataclass
class FakeResponse:
    payload: dict

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeSession:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict]] = []

    def post(self, url: str, json: dict | None = None, timeout: int | None = None):
        self.calls.append((url, json or {}))
        if not self._responses:
            raise AssertionError("No response queued")
        return FakeResponse(self._responses.pop(0))


class FakeCookieJar:
    def __init__(self) -> None:
        self.set_calls: list[tuple[str, str, str, str]] = []

    def set(self, key: str, value: str, domain: str, path: str) -> None:
        self.set_calls.append((key, value, domain, path))


class FakeLoginResponse:
    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None


class FakeLoginSession:
    def __init__(self, text: str) -> None:
        self._text = text
        self.cookies = FakeCookieJar()
        self.last_post: tuple[str, dict] | None = None

    def post(self, url: str, data: dict | None = None, timeout: int | None = None):
        self.last_post = (url, data or {})
        return FakeLoginResponse(self._text)


def test_csv_suffix_sanitizes_formats():
    assert _csv_suffix("") == ""
    assert _csv_suffix("gpx") == ""
    assert _csv_suffix("g3x") == ".g3x"
    assert _csv_suffix("garmin g3x") == ".garmin_g3x"
    assert _csv_suffix("fr24+csv") == ".fr24_csv"


def test_extract_cookie_and_api_base():
    html = 'setCookie("SID3","abc123"); setCookie("USER3","u");'
    assert _extract_cookie(html, "SID3") == "abc123"
    assert _extract_cookie(html, "MISSING") is None
    assert _api_base("https://api.cloudahoy.com") == "https://www.cloudahoy.com/api"
    assert _api_base("https://www.cloudahoy.com/api/") == "https://www.cloudahoy.com/api"


def test_build_auth_payload_variants():
    payload = _build_auth_payload({"EMAIL3": "e", "SID3": "s", "USER3": "u"}, initial_call=True)
    assert payload["initialCall"] is True
    assert payload["EMAIL3"] == "e"
    assert payload["wlh"].endswith("/flights/")
    assert payload["BI"].startswith("CLI")

    payload = _build_auth_payload({"EMAIL3": "e"}, initial_call=False)
    assert payload["initialCall"] is False
    assert payload["wlh"].endswith("/debrief/")


def test_extract_last_token_and_from_unix():
    flights = [{"gmtStart": 123.4}, {"adjTime": "567.8"}]
    assert _extract_last_token(flights) == "zz14[d-mmm-yy HH:MM]567zz14"
    assert _extract_last_token([]) is None

    ts = _from_unix(100)
    assert isinstance(ts, datetime)
    assert ts.tzinfo == timezone.utc

    fallback = _from_unix("bad")
    assert isinstance(fallback, datetime)
    assert fallback.tzinfo == timezone.utc


def test_extract_fdid_and_kml():
    payload = {"flt": {"Meta": {"fdID": "meta-id"}}}
    assert _extract_fdid_from_payload(payload) == "meta-id"

    payload = {"flt": {"fdID": "root-id"}}
    assert _extract_fdid_from_payload(payload) == "root-id"

    payload = {"flt": {"KML": {"k": "<?xml version=\"1.0\"?><kml></kml>"}}}
    assert _extract_kml(payload).startswith("<?xml")

    payload = {"flt": {"KML": "<?xml version=\"1.0\"?><kml></kml>"}}
    assert _extract_kml(payload).startswith("<?xml")


def test_normalize_tail_number_and_metadata():
    tail, aircraft_type, raw = _normalize_tail_number(["N123AB", "Cessna 172", "UNKNOWN"])
    assert tail == "N123AB"
    assert aircraft_type == "Cessna 172"
    assert raw == ["N123AB", "Cessna 172", "UNKNOWN"]

    tail, aircraft_type, raw = _normalize_tail_number("UNKNOWN")
    assert tail is None
    assert aircraft_type is None
    assert raw == ["UNKNOWN"]

    assert _is_tail_candidate("N123AB")
    assert _is_tail_candidate("D-ABCD")
    assert _matches_tail_pattern("D-ABCD")
    assert not _is_tail_candidate("OTHER")
    assert not _matches_tail_pattern("BAD-")

    flt = {
        "Meta": {
            "pilot": "Ada",
            "tailNumber": ["N123AB", "Cessna 172"],
            "summary": {"air": {"start": 100.0}},
        }
    }
    meta = _extract_metadata(flt)
    assert meta["pilot"] == "Ada"
    assert meta["tail_number"] == "N123AB"
    assert meta["aircraft_type"] == "Cessna 172"


def test_list_flights_paginates_and_dedupes(monkeypatch):
    responses = [
        {
            "flights": [
                {
                    "key": "A1",
                    "gmtStart": 1000,
                    "nSec": 10,
                    "aircraft": {"P": {"typeAircraft": "C172"}},
                    "tailNumber": "N1",
                },
                {"fdID": "A2", "adjTime": 2000, "nSec": 20, "aircraft": {"tailNumber": "N2"}},
            ],
            "more": True,
        },
        {
            "flights": [
                {"key": "A1", "gmtStart": 1001, "nSec": 11},
                {"fdID": "A3", "gmtStart": 3000, "nSec": 30},
            ],
            "more": False,
        },
    ]
    session = FakeSession(responses)

    def fake_login(base_url: str, email: str, password: str):
        return session, {"EMAIL3": "e", "SID3": "s", "USER3": "u"}

    monkeypatch.setattr("src.core.cloudahoy.client._login", fake_login)

    client = CloudAhoyClient(
        api_key=None,
        base_url="https://www.cloudahoy.com/api",
        email="user",
        password="pass",
        exports_dir=None,  # type: ignore[arg-type]
    )
    flights = client.list_flights()
    assert [flight.id for flight in flights] == ["A1", "A2", "A3"]
    assert session.calls[0][0].endswith("/t-flights.cgi")
    assert session.calls[0][1]["initialCall"] is True
    assert session.calls[1][1]["initialCall"] is False


def test_fetch_flight_exports_files(tmp_path, monkeypatch):
    payload = {
        "flt": {
            "points": [
                [-122.0, 47.0, 100.0],
                [-122.1, 47.1, 110.0],
            ],
            "Meta": {"tailNumber": "N123AB", "air": 0.1, "gnd": 0.1},
        }
    }

    def fake_fetch_raw(self, flight_id: str):
        return payload

    monkeypatch.setattr(CloudAhoyClient, "_fetch_raw", fake_fetch_raw)

    client = CloudAhoyClient(
        api_key=None,
        base_url="https://www.cloudahoy.com/api",
        email="user",
        password="pass",
        exports_dir=tmp_path,
        export_formats=["g3x", "gpx"],
    )

    detail = client.fetch_flight("A1")
    assert detail.file_type == "g3x"
    assert detail.file_path
    assert detail.csv_path
    assert detail.raw_path
    assert detail.metadata_path

    assert (tmp_path / "A1.cloudahoy.json").exists()
    assert (tmp_path / "A1.g3x.csv").exists()
    assert (tmp_path / "A1.gpx").exists()
    assert (tmp_path / "A1.meta.json").exists()


def test_fetch_flight_falls_back_to_kml(tmp_path, monkeypatch):
    payload = {
        "flt": {
            "KML": "<?xml version=\"1.0\"?><kml></kml>",
            "Meta": {"tailNumber": "N123AB"},
        }
    }

    def fake_fetch_raw(self, flight_id: str):
        return payload

    monkeypatch.setattr(CloudAhoyClient, "_fetch_raw", fake_fetch_raw)

    client = CloudAhoyClient(
        api_key=None,
        base_url="https://www.cloudahoy.com/api",
        email="user",
        password="pass",
        exports_dir=tmp_path,
    )

    detail = client.fetch_flight("A2")
    assert detail.file_type == "kml"
    assert (tmp_path / "A2.kml").exists()
    assert (tmp_path / "A2.meta.json").exists()


def test_fetch_metadata(monkeypatch):
    payload = {"flt": {"Meta": {"pilot": "Ada", "tailNumber": "N42"}}}

    def fake_fetch_raw(self, flight_id: str):
        return payload

    monkeypatch.setattr(CloudAhoyClient, "_fetch_raw", fake_fetch_raw)

    client = CloudAhoyClient(
        api_key=None,
        base_url="https://www.cloudahoy.com/api",
        email="user",
        password="pass",
        exports_dir=None,  # type: ignore[arg-type]
    )

    meta = client.fetch_metadata("A3")
    assert meta["pilot"] == "Ada"
    assert meta["tail_number"] == "N42"


def test_login_sets_cookies(monkeypatch):
    html = "\n".join(
        [
            'setCookie("SID3","sid");',
            'setCookie("USER3","user");',
            'setCookie("EMAIL3","email@example.com");',
        ]
    )
    session = FakeLoginSession(html)

    def fake_session() -> FakeLoginSession:
        return session

    monkeypatch.setattr("src.core.cloudahoy.client.requests.Session", fake_session)

    session_out, auth = _login("https://api.cloudahoy.com", "user@example.com", "pass")
    assert session_out is session
    assert auth["SID3"] == "sid"
    assert session.last_post
    assert session.last_post[0].endswith("/signin.cgi?form")
    assert session.last_post[1]["email"] == "user@example.com"
    assert session.cookies.set_calls
    assert session.cookies.set_calls[0][2] == "www.cloudahoy.com"


def test_login_raises_on_missing_cookie(monkeypatch):
    session = FakeLoginSession('setCookie("SID3","sid");')

    def fake_session() -> FakeLoginSession:
        return session

    monkeypatch.setattr("src.core.cloudahoy.client.requests.Session", fake_session)

    with pytest.raises(RuntimeError):
        _login("https://www.cloudahoy.com/api", "user@example.com", "pass")
