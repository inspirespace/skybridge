from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from src.models import FlightDetail, FlightSummary
from src.web.browser import BrowserOptions, BrowserSession


@dataclass(frozen=True)
class CloudAhoyWebConfig:
    base_url: str
    email: str | None
    password: str | None
    flights_url: str | None
    export_url_template: str | None
    debrief_url_template: str | None
    storage_state_path: Path
    downloads_dir: Path
    headless: bool


class CloudAhoyWebClient:
    def __init__(self, config: CloudAhoyWebConfig) -> None:
        self._config = config

    def list_flights(self, limit: int | None = None) -> list[FlightSummary]:
        session = self._open_session()
        page = session.open()
        responses: list[dict[str, Any]] = []
        session.on_response(lambda url, data: self._record_response(url, data, responses))

        self._ensure_login(page)
        flights_url = self._config.flights_url or self._guess_flights_url(page)
        if not flights_url:
            session.close()
            raise RuntimeError(
                "Unable to locate flights page. Set CLOUD_AHOY_FLIGHTS_URL."
            )

        page.goto(flights_url, wait_until="networkidle")

        summaries = self._extract_flights(page, responses)
        if limit:
            summaries = summaries[:limit]

        session.save_state()
        session.close()
        return summaries

    def fetch_flight(self, flight_id: str) -> FlightDetail:
        if not self._config.export_url_template:
            raise RuntimeError(
                "CLOUD_AHOY_EXPORT_URL_TEMPLATE is required for web export."
            )

        session = self._open_session()
        page = session.open()
        self._ensure_login(page)

        cesium_files = self.capture_cesium(flight_id)

        export_url = self._config.export_url_template.format(flight_id=flight_id)
        download_path = self._download_file(page, export_url)

        session.save_state()
        session.close()

        return FlightDetail(
            id=flight_id,
            raw_payload={
                "source": "cloudahoy",
                "export_url": export_url,
                "cesium_files": [str(path) for path in cesium_files],
            },
            file_path=str(download_path),
            file_type=download_path.suffix.lstrip(".") or None,
        )

    def capture_cesium(self, flight_id: str) -> list[Path]:
        session = self._open_session()
        page = session.open()
        self._ensure_login(page)

        captures: list[Path] = []
        seen_urls: set[str] = set()

        def handle_response(response) -> None:
            url = response.url
            if url in seen_urls:
                return
            content_type = response.headers.get("content-type", "")
            if not _is_cesium_candidate(url, content_type):
                return
            try:
                body = response.text()
            except Exception:
                return
            if not body:
                return
            seen_urls.add(url)
            suffix = "czml" if "czml" in url or "czml" in content_type else "json"
            self._config.downloads_dir.mkdir(parents=True, exist_ok=True)
            path = self._config.downloads_dir / f"{flight_id}.cesium.{len(captures)+1}.{suffix}"
            path.write_text(body)
            captures.append(path)

        page.on("response", handle_response)
        for url in self._debrief_url_candidates(flight_id):
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(2000)
            if captures:
                break

        session.save_state()
        session.close()
        return captures

    def _open_session(self) -> BrowserSession:
        options = BrowserOptions(
            headless=self._config.headless,
            storage_state_path=self._config.storage_state_path,
        )
        return BrowserSession(options)

    def _ensure_login(self, page: Page) -> None:
        page.goto(f"{self._config.base_url}/login.php", wait_until="networkidle")
        if page.locator("form#ca_loginform").count() == 0:
            return
        if not self._config.email or not self._config.password:
            raise RuntimeError(
                "CloudAhoy login required. Set CLOUD_AHOY_EMAIL and CLOUD_AHOY_PASSWORD."
            )
        page.fill("input[name=email]", self._config.email)
        page.fill("input[name=password]", self._config.password)
        page.click("#btnlogin")
        page.wait_for_load_state("load")

    def _guess_flights_url(self, page: Page) -> str | None:
        links = page.locator("a")
        for idx in range(min(links.count(), 50)):
            href = links.nth(idx).get_attribute("href")
            if not href:
                continue
            if "debrief" in href or "flight" in href:
                if href.startswith("http"):
                    return href
                return f"{self._config.base_url}/{href.lstrip('/')}"
        return None

    def _record_response(
        self, url: str, data: dict | list | None, responses: list[dict[str, Any]]
    ) -> None:
        if data is None:
            return
        if "flight" in url or "debrief" in url or "log" in url:
            responses.append({"url": url, "data": data})

    def _extract_flights(
        self, page: Page, responses: list[dict[str, Any]]
    ) -> list[FlightSummary]:
        summaries: list[FlightSummary] = []

        for payload in responses:
            extracted = _extract_flight_items(payload.get("data"))
            summaries.extend(extracted)

        if summaries:
            return summaries

        dom_items = page.evaluate(
            """
            () => {
                const items = [];
                document.querySelectorAll('[data-flight-id], [data-debrief-id]').forEach((el) => {
                    const id = el.getAttribute('data-flight-id') || el.getAttribute('data-debrief-id');
                    if (id) {
                        items.push({id});
                    }
                });
                return items;
            }
            """
        )

        for item in dom_items:
            summaries.append(
                FlightSummary(
                    id=str(item.get("id")),
                    started_at=datetime.utcnow(),
                    duration_seconds=None,
                    aircraft_type=None,
                    tail_number=None,
                )
            )

        if not summaries:
            raise RuntimeError(
                "No flights found. Provide CLOUD_AHOY_FLIGHTS_URL or export URL template."
            )
        return summaries

    def _download_file(self, page: Page, export_url: str) -> Path:
        self._config.downloads_dir.mkdir(parents=True, exist_ok=True)
        with page.expect_download() as download_info:
            page.goto(export_url, wait_until="networkidle")
        download = download_info.value
        filename = download.suggested_filename
        if not filename:
            filename = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.export"
        destination = self._config.downloads_dir / filename
        download.save_as(destination)
        return destination

    def _debrief_url_candidates(self, flight_id: str) -> list[str]:
        if self._config.debrief_url_template:
            return [self._config.debrief_url_template.format(flight_id=flight_id)]
        base = self._config.base_url.rstrip("/")
        return [
            f"{base}/debrief/?flight={flight_id}",
            f"{base}/debrief/?id={flight_id}",
            f"{base}/debrief/?f={flight_id}",
            f"{base}/debrief/?key={flight_id}",
            f"{base}/debrief/index.php?flight={flight_id}",
        ]


def _is_cesium_candidate(url: str, content_type: str) -> bool:
    lowered = url.lower()
    if "czml" in lowered or "cesium" in lowered:
        return True
    if "czml" in content_type.lower():
        return True
    return False


def _extract_flight_items(data: Any) -> list[FlightSummary]:
    if not data:
        return []
    flights: list[FlightSummary] = []

    def handle_item(item: dict) -> None:
        flight_id = item.get("id") or item.get("flight_id") or item.get("debrief_id")
        if not flight_id:
            return
        started_at_raw = item.get("started_at") or item.get("start_time") or item.get("date")
        try:
            started_at = (
                datetime.fromisoformat(started_at_raw)
                if isinstance(started_at_raw, str)
                else datetime.utcnow()
            )
        except ValueError:
            started_at = datetime.utcnow()
        flights.append(
            FlightSummary(
                id=str(flight_id),
                started_at=started_at,
                duration_seconds=item.get("duration_seconds"),
                aircraft_type=item.get("aircraft_type"),
                tail_number=item.get("tail_number"),
            )
        )

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                handle_item(item)
        return flights

    if isinstance(data, dict):
        for key in ("flights", "debriefs", "items"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        handle_item(item)
        return flights

    return flights
