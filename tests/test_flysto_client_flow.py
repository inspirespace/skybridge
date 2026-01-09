"""tests/test_flysto_client_flow.py module."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
import requests

import src.core.flysto.client as flysto_mod
from src.core.flysto.client import FlyStoClient
from src.core.models import FlightDetail


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "{}"


class DummySession:
    def __init__(self, responses=None, raises=None):
        self.responses = list(responses or [])
        self.raises = list(raises or [])
        self.calls = []
        self.cookies = requests.cookies.RequestsCookieJar()

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if self.raises:
            raise self.raises.pop(0)
        if self.responses:
            return self.responses.pop(0)
        return DummyResponse()


def test_prepare_sets_cookie_and_version(monkeypatch):
    client = FlyStoClient(api_key="", base_url="https://example.test")

    def fake_ensure(session):
        session.cookies.set("USER_SESSION", "cookie", domain="example.test", path="/")

    monkeypatch.setattr(client, "_ensure_session", fake_ensure)
    monkeypatch.setattr(flysto_mod, "_infer_api_version", lambda _base: "42")

    assert client.prepare() is True
    assert client.session_cookie == "cookie"
    assert client.api_version == "42"


def test_prepare_returns_false_without_cookie(monkeypatch):
    client = FlyStoClient(api_key="", base_url="https://example.test")
    monkeypatch.setattr(client, "_ensure_session", lambda _session: None)
    assert client.prepare() is False


def test_upload_flight_success_sets_cache(tmp_path: Path, monkeypatch):
    file_path = tmp_path / "flight.gpx"
    file_path.write_text("data")
    client = FlyStoClient(api_key="", base_url="https://example.test")

    monkeypatch.setattr(client, "_ensure_session", lambda _session: None)
    monkeypatch.setattr(flysto_mod, "_infer_api_version", lambda _base: "7")

    def fake_request(session, method, url, **kwargs):
        return DummyResponse(text='{"signature":"flight.gpx/sig/log1","logId":"log1","logFormatId":"gpx"}')

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.upload_flight(FlightDetail(id="f1", raw_payload={}, file_path=str(file_path)))
    assert result.log_id == "log1"
    assert client.upload_cache["flight.gpx"].log_id == "log1"


def test_upload_flight_duplicate_error(tmp_path: Path, monkeypatch):
    file_path = tmp_path / "flight.gpx"
    file_path.write_text("data")
    client = FlyStoClient(api_key="", base_url="https://example.test")
    monkeypatch.setattr(client, "_ensure_session", lambda _session: None)

    def fake_request(session, method, url, **kwargs):
        return DummyResponse(status_code=409, text="duplicate")

    monkeypatch.setattr(client, "_request", fake_request)

    with pytest.raises(RuntimeError, match="duplicate upload"):
        client.upload_flight(FlightDetail(id="f1", raw_payload={}, file_path=str(file_path)))


def test_upload_flight_dry_run_skips_request(tmp_path: Path, monkeypatch):
    file_path = tmp_path / "flight.gpx"
    file_path.write_text("data")
    client = FlyStoClient(api_key="", base_url="https://example.test")
    called = {"count": 0}

    def fake_request(*_args, **_kwargs):
        called["count"] += 1
        return DummyResponse()

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.upload_flight(
        FlightDetail(id="f1", raw_payload={}, file_path=str(file_path)),
        dry_run=True,
    )
    assert result is None
    assert called["count"] == 0


def test_ensure_session_uses_cookie(tmp_path: Path):
    client = FlyStoClient(api_key="", base_url="https://example.test")
    client.session_cookie = "cookie"
    session = requests.Session()
    client._ensure_session(session)
    assert session.cookies.get("USER_SESSION") == "cookie"


def test_ensure_session_uses_login(monkeypatch):
    client = FlyStoClient(
        api_key="",
        base_url="https://example.test",
        email="user",
        password="pass",
    )
    session = requests.Session()

    def fake_api_login(sess, *_args, **_kwargs):
        sess.cookies.set("USER_SESSION", "cookie", domain="example.test", path="/")

    monkeypatch.setattr(flysto_mod, "_api_login", fake_api_login)
    client._ensure_session(session)
    assert session.cookies.get("USER_SESSION") == "cookie"


def test_ensure_session_raises_without_cookie(monkeypatch):
    client = FlyStoClient(
        api_key="",
        base_url="https://example.test",
        email="user",
        password="pass",
    )
    session = requests.Session()
    monkeypatch.setattr(flysto_mod, "_api_login", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError):
        client._ensure_session(session)


def test_request_retries_on_status(monkeypatch):
    client = FlyStoClient(api_key="", base_url="https://example.test")
    client.max_request_retries = 3
    client.min_request_interval = 0
    session = DummySession(
        responses=[DummyResponse(status_code=429), DummyResponse(status_code=503), DummyResponse(status_code=200)],
    )
    monkeypatch.setattr(flysto_mod.time, "sleep", lambda *_args, **_kwargs: None)
    response = client._request(session, "get", "https://example.test")
    assert response.status_code == 200


def test_request_raises_last_error(monkeypatch):
    client = FlyStoClient(api_key="", base_url="https://example.test")
    client.max_request_retries = 2
    client.min_request_interval = 0
    session = DummySession(raises=[requests.RequestException("boom"), requests.RequestException("boom")])
    monkeypatch.setattr(flysto_mod.time, "sleep", lambda *_args, **_kwargs: None)
    with pytest.raises(requests.RequestException):
        client._request(session, "get", "https://example.test")


def test_request_sets_api_version_header(monkeypatch):
    client = FlyStoClient(api_key="", base_url="https://example.test")
    client.api_version = "9"
    client.min_request_interval = 0
    session = DummySession(responses=[DummyResponse(status_code=200)])
    response = client._request(session, "get", "https://example.test")
    assert response.status_code == 200
    method, url, kwargs = session.calls[-1]
    assert kwargs["headers"]["x-version"] == "9"
