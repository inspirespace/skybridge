"""Tests for BrowserSession."""
from __future__ import annotations

from pathlib import Path

import pytest

import src.core.web.browser as browser


class DummyRequest:
    def __init__(self, url: str, method: str = "GET", post_data: str | None = None):
        self.url = url
        self.method = method
        self.headers = {"Content-Type": "application/json"}
        self._post_data = post_data

    def post_data(self):
        return self._post_data


class DummyResponse:
    def __init__(self, url: str, content_type: str, json_value=None, text_value=""):
        self.url = url
        self.headers = {"content-type": content_type}
        self._json = json_value
        self._text = text_value

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json

    def text(self):
        return self._text


class DummyPage:
    def __init__(self):
        self._listeners = {}

    def on(self, name: str, handler):
        self._listeners[name] = handler

    def emit_request(self, request: DummyRequest):
        self._listeners["request"](request)

    def emit_response(self, response: DummyResponse):
        self._listeners["response"](response)


class DummyContext:
    def __init__(self, page: DummyPage):
        self._page = page
        self.storage_path = None

    def new_page(self):
        return self._page

    def storage_state(self, path: str):
        self.storage_path = path

    def close(self):
        return None


class DummyBrowser:
    def __init__(self, page: DummyPage):
        self._page = page

    def new_context(self, storage_state: str | None = None):
        return DummyContext(self._page)

    def close(self):
        return None


class DummyPlaywright:
    def __init__(self, page: DummyPage):
        self._page = page
        self.chromium = self

    def launch(self, headless: bool, slow_mo: int):
        return DummyBrowser(self._page)

    def start(self):
        return self

    def stop(self):
        return None


def test_browser_session_handlers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    page = DummyPage()
    dummy = DummyPlaywright(page)
    monkeypatch.setattr(browser, "sync_playwright", lambda: dummy)

    options = browser.BrowserOptions(headless=True, storage_state_path=None)
    session = browser.BrowserSession(options)
    session.open()

    requests = []
    responses = []
    session.on_request(lambda url, method, headers, post_data: requests.append((url, method, post_data)))
    session.on_response(lambda url, data: responses.append((url, data)))

    page.emit_request(DummyRequest("https://example.com", "POST", "data"))
    page.emit_response(DummyResponse("https://example.com/api", "application/json", {"ok": True}))

    assert requests[0][0] == "https://example.com"
    assert responses[0][1] == {"ok": True}

    session.save_state()
    session.close()
