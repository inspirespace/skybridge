"""Tests for CloudAhoy web helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.core.web.cloudahoy import CloudAhoyWebClient, CloudAhoyWebConfig, _extract_flight_items


class DummyLocator:
    def __init__(self, hrefs=None, count=0, disabled=False, on_click=None):
        self._hrefs = hrefs or []
        self._count = count
        self._disabled = disabled
        self._on_click = on_click
        self.first = self

    def count(self):
        return self._count or len(self._hrefs)

    def nth(self, idx: int):
        return DummyLocator([self._hrefs[idx]])

    def get_attribute(self, _name: str):
        return self._hrefs[0] if self._hrefs else None

    def is_disabled(self):
        return self._disabled

    def click(self):
        if self._on_click:
            self._on_click()
        return None


class DummyPage:
    def __init__(self, links=None, login=True, load_more=False):
        self._links = links or []
        self._login = login
        self._load_more = load_more
        self.clicked = 0
        self._evaluate_payload = []

        class DummyMouse:
            def __init__(self, page):
                self._page = page

            def wheel(self, *_args, **_kwargs):
                self._page.clicked += 1

        self.mouse = DummyMouse(self)

    def locator(self, selector: str):
        if selector == "a":
            return DummyLocator(self._links)
        if selector == "form#ca_loginform":
            return DummyLocator(count=1 if self._login else 0)
        if "Load more" in selector and self._load_more:
            return DummyLocator(count=1, on_click=self._handle_click)
        return DummyLocator(count=0)

    def goto(self, *_args, **_kwargs):
        return None

    def fill(self, *_args, **_kwargs):
        return None

    def click(self, *_args, **_kwargs):
        return None

    def wait_for_load_state(self, *_args, **_kwargs):
        return None

    def wait_for_timeout(self, *_args, **_kwargs):
        return None

    def evaluate(self, *_args, **_kwargs):
        return self._evaluate_payload

    def set_dom_items(self, items):
        self._evaluate_payload = items

    def _handle_click(self):
        self.clicked += 1



def _config(tmp_path: Path) -> CloudAhoyWebConfig:
    return CloudAhoyWebConfig(
        base_url="https://cloudahoy",
        email=None,
        password=None,
        flights_url=None,
        export_url_template=None,
        storage_state_path=tmp_path / "state.json",
        downloads_dir=tmp_path / "downloads",
        headless=True,
    )


def test_guess_flights_url() -> None:
    client = CloudAhoyWebClient(_config(Path("/tmp")))
    page = DummyPage(["/debrief/123"], login=False)
    url = client._guess_flights_url(page)
    assert url == "https://cloudahoy/debrief/123"


def test_guess_flights_url_absolute() -> None:
    client = CloudAhoyWebClient(_config(Path("/tmp")))
    page = DummyPage(["https://cloudahoy/flights"], login=False)
    url = client._guess_flights_url(page)
    assert url == "https://cloudahoy/flights"


def test_ensure_login_requires_creds(tmp_path: Path) -> None:
    client = CloudAhoyWebClient(_config(tmp_path))
    with pytest.raises(RuntimeError):
        client._ensure_login(DummyPage(login=True))


def test_extract_flight_items() -> None:
    data = {"items": [{"id": "f1", "started_at": "2026-01-01T10:00:00"}]}
    flights = _extract_flight_items(data)
    assert flights[0].id == "f1"


def test_record_response_filters() -> None:
    client = CloudAhoyWebClient(_config(Path("/tmp")))
    responses = []
    client._record_response("https://cloudahoy/api/flight", {"items": []}, responses)
    client._record_response("https://cloudahoy/api/other", {"items": []}, responses)
    client._record_response("https://cloudahoy/api/log", None, responses)
    assert len(responses) == 1


def test_extract_flights_from_responses(tmp_path: Path) -> None:
    client = CloudAhoyWebClient(_config(tmp_path))
    page = DummyPage(login=False)
    responses = [{"data": [{"id": "f2", "started_at": "2026-01-02T10:00:00"}]}]
    flights = client._extract_flights(page, responses)
    assert flights[0].id == "f2"
    assert isinstance(flights[0].started_at, datetime)


def test_extract_flights_from_dom_fallback(tmp_path: Path) -> None:
    client = CloudAhoyWebClient(_config(tmp_path))
    page = DummyPage(login=False)
    page.set_dom_items([{"id": "dom-1"}])
    flights = client._extract_flights(page, [])
    assert flights[0].id == "dom-1"
    assert flights[0].started_at.tzinfo == timezone.utc


def test_load_more_flights_respects_limit(tmp_path: Path) -> None:
    client = CloudAhoyWebClient(_config(tmp_path))
    page = DummyPage(load_more=True)
    responses = [{"data": [{"id": "f1"}]}]
    client._load_more_flights(page, responses, limit=1)
    assert page.clicked == 0


def test_load_more_flights_clicks_button(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = CloudAhoyWebClient(_config(tmp_path))
    page = DummyPage(load_more=True)
    responses: list[dict] = []
    counts = [0, 1, 1, 1]

    def fake_count(_responses):
        return counts.pop(0) if counts else 1

    monkeypatch.setattr(client, "_count_flights_from_responses", fake_count)
    monkeypatch.setattr(client, "_dom_flight_count", lambda _page: 0)
    client._load_more_flights(page, responses, limit=None)
    assert page.clicked >= 1
