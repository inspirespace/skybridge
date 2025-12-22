from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page

from src.models import FlightDetail
from src.web.browser import BrowserOptions, BrowserSession


@dataclass(frozen=True)
class FlyStoWebConfig:
    base_url: str
    email: str | None
    password: str | None
    upload_url: str | None
    storage_state_path: Path
    headless: bool


class FlyStoWebClient:
    def __init__(self, config: FlyStoWebConfig) -> None:
        self._config = config

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> None:
        if dry_run:
            return
        if not flight.file_path:
            raise RuntimeError("Flight export file is required for FlySto upload")

        session = self._open_session()
        page = session.open()
        self._ensure_login(page)

        self._navigate_to_upload(page)
        self._upload_file(page, Path(flight.file_path))

        session.save_state()
        session.close()

    def _open_session(self) -> BrowserSession:
        options = BrowserOptions(
            headless=self._config.headless,
            storage_state_path=self._config.storage_state_path,
        )
        return BrowserSession(options)

    def _ensure_login(self, page: Page) -> None:
        page.goto(f"{self._config.base_url}/login", wait_until="networkidle")
        if page.locator("input[name=email]").count() == 0:
            return
        if not self._config.email or not self._config.password:
            raise RuntimeError("FlySto login required. Set FLYSTO_EMAIL and FLYSTO_PASSWORD.")
        page.fill("input[name=email]", self._config.email)
        page.fill("input[name=password]", self._config.password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")

    def _navigate_to_upload(self, page: Page) -> None:
        if self._config.upload_url:
            page.goto(self._config.upload_url, wait_until="networkidle")
            return

        page.goto(f"{self._config.base_url}/logs", wait_until="networkidle")
        if page.locator("input[type=file]").count() > 0:
            return

        upload_triggers = ["Upload", "Add flight", "Import", "Upload flight"]
        for label in upload_triggers:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                page.wait_for_load_state("networkidle")
                if page.locator("input[type=file]").count() > 0:
                    return
        raise RuntimeError(
            "Unable to find upload form. Set FLYSTO_UPLOAD_URL to the upload page."
        )

    def _upload_file(self, page: Page, file_path: Path) -> None:
        file_input = page.locator("input[type=file]").first
        file_input.set_input_files(str(file_path))

        submit_buttons = ["Upload", "Import", "Submit", "Save"]
        for label in submit_buttons:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                break
        page.wait_for_load_state("networkidle")
