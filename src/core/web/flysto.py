"""src/core/web/flysto.py module."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Page

from src.core.models import FlightDetail
from src.core.web.browser import BrowserOptions, BrowserSession


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
        """Internal helper for init  ."""
        self._config = config

    def upload_flight(self, flight: FlightDetail, dry_run: bool = False) -> None:
        """Handle upload flight."""
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
        """Internal helper for open session."""
        options = BrowserOptions(
            headless=self._config.headless,
            storage_state_path=self._config.storage_state_path,
        )
        return BrowserSession(options)

    def _ensure_login(self, page: Page) -> None:
        """Internal helper for ensure login."""
        page.goto(f"{self._config.base_url}/login", wait_until="networkidle")
        email_input = page.locator(
            "input[name=email], input[type='email'], input[placeholder*='email' i]"
        )
        if email_input.count() == 0:
            return
        if not self._config.email or not self._config.password:
            raise RuntimeError("FlySto login required. Set FLYSTO_EMAIL and FLYSTO_PASSWORD.")
        password_input = page.locator(
            "input[name=password], input[type='password'], input[placeholder*='password' i]"
        )
        if password_input.count() == 0:
            raise RuntimeError("FlySto login password input not found.")
        email_input.first.fill(self._config.email)
        password_input.first.fill(self._config.password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("load")

    def _navigate_to_upload(self, page: Page) -> None:
        """Internal helper for navigate to upload."""
        if self._config.upload_url:
            page.goto(self._config.upload_url, wait_until="networkidle")
            return

        page.goto(f"{self._config.base_url}/logs", wait_until="networkidle")
        page.wait_for_timeout(2000)
        upload_triggers = ["Load logs", "Upload", "Add flight", "Import", "Upload flight"]
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
        """Internal helper for upload file."""
        file_inputs = page.locator("input[type=file]")
        if file_inputs.count() == 0 and page.get_by_text("Browse files").count() > 0:
            page.get_by_text("Browse files").first.click()
            page.wait_for_timeout(1000)
            file_inputs = page.locator("input[type=file]")
        if file_inputs.count() == 0:
            raise RuntimeError("FlySto upload input not found after opening modal.")

        file_input = file_inputs.first
        file_input.set_input_files(str(file_path))

        submit_buttons = ["Upload", "Import", "Submit", "Save"]
        for label in submit_buttons:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                break
        page.wait_for_load_state("networkidle")
