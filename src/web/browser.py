from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright


@dataclass
class BrowserOptions:
    headless: bool
    storage_state_path: Path | None
    slow_mo_ms: int = 0


class BrowserSession:
    def __init__(self, options: BrowserOptions) -> None:
        self._options = options
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def open(self) -> Page:
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=self._options.headless,
            slow_mo=self._options.slow_mo_ms or 0,
        )
        if self._options.storage_state_path and self._options.storage_state_path.exists():
            self._context = self._browser.new_context(
                storage_state=str(self._options.storage_state_path)
            )
        else:
            self._context = self._browser.new_context()
        self._page = self._context.new_page()
        return self._page

    def on_response(self, handler: Callable[[str, dict | None], None]) -> None:
        if not self._page:
            raise RuntimeError("BrowserSession is not open")

        def _handle(response) -> None:
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                return
            try:
                data = response.json()
            except Exception:
                data = None
            handler(response.url, data)

        self._page.on("response", _handle)

    def on_request(self, handler: Callable[[str, str, dict, str | None], None]) -> None:
        if not self._page:
            raise RuntimeError("BrowserSession is not open")

        def _handle(request) -> None:
            post_data = None
            if request.method.upper() != "GET":
                post_data_attr = request.post_data
                post_data = post_data_attr() if callable(post_data_attr) else post_data_attr
            handler(request.url, request.method, request.headers, post_data)

        self._page.on("request", _handle)

    def save_state(self) -> None:
        if self._context and self._options.storage_state_path:
            self._context.storage_state(path=str(self._options.storage_state_path))

    def close(self) -> None:
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
