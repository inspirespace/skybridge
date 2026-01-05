"""src/core/discovery.py module."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from src.core.web.browser import BrowserOptions, BrowserSession


@dataclass(frozen=True)
class DiscoveryConfig:
    cloudahoy_base_url: str
    cloudahoy_email: str | None
    cloudahoy_password: str | None
    flysto_base_url: str
    flysto_email: str | None
    flysto_password: str | None
    headless: bool
    output_dir: Path
    cloudahoy_flights_url: str | None = None
    cloudahoy_export_url_template: str | None = None
    flysto_upload_url: str | None = None
    upload_file: Path | None = None


def run_discovery(config: DiscoveryConfig) -> Path:
    """Handle run discovery."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "cloudahoy": discover_cloudahoy(config),
        "flysto": discover_flysto(config),
    }
    output_path = config.output_dir / "discovery.json"
    output_path.write_text(json.dumps(results, indent=2))
    return output_path


def discover_cloudahoy(config: DiscoveryConfig) -> dict[str, Any]:
    """Handle discover cloudahoy."""
    session = BrowserSession(
        BrowserOptions(headless=config.headless, storage_state_path=None)
    )
    page = session.open()

    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []
    session.on_request(
        lambda url, method, headers, post_data: _log_request(
            url, method, headers, post_data, request_log
        )
    )
    session.on_response(lambda url, data: _log_response(url, data, response_log))

    _login_cloudahoy(page, config)

    flights_url = config.cloudahoy_flights_url or _guess_flights_url(page, config.cloudahoy_base_url)
    if flights_url:
        page.goto(flights_url, wait_until="networkidle")

    export_url = config.cloudahoy_export_url_template
    if not export_url:
        export_url = _click_export_button(page)

    session.close()

    inferred_template = _infer_template_from_url(export_url) if export_url else None

    return {
        "flights_url": flights_url,
        "export_url": export_url,
        "export_url_template": inferred_template,
        "requests": request_log,
        "responses": response_log,
    }


def discover_flysto(config: DiscoveryConfig) -> dict[str, Any]:
    """Handle discover flysto."""
    session = BrowserSession(
        BrowserOptions(headless=config.headless, storage_state_path=None)
    )
    page = session.open()

    request_log: list[dict[str, Any]] = []
    response_log: list[dict[str, Any]] = []
    session.on_request(
        lambda url, method, headers, post_data: _log_request(
            url, method, headers, post_data, request_log
        )
    )
    session.on_response(lambda url, data: _log_response(url, data, response_log))
    page.on(
        "response",
        lambda response: _log_response_raw(response, response_log),
    )

    _login_flysto(page, config)

    if config.flysto_upload_url:
        page.goto(config.flysto_upload_url, wait_until="networkidle")
    else:
        page.goto(f"{config.flysto_base_url}/logs", wait_until="networkidle")

    upload_url = None
    if config.upload_file:
        upload_url = _attempt_upload(page, config.upload_file)

    session.close()

    return {
        "upload_url": upload_url,
        "requests": request_log,
        "responses": response_log,
    }


def _log_response_raw(response, log: list[dict[str, Any]]) -> None:
    """Internal helper for log response raw."""
    url = response.url
    if "flysto.net/api" not in url:
        return
    content_type = response.headers.get("content-type", "")
    payload: Any = None
    try:
        if "application/json" in content_type:
            payload = response.json()
        else:
            text = response.text()
            if text and len(text) < 5000:
                payload = text
    except Exception:
        payload = None
    if isinstance(payload, dict):
        payload = _redact_json(payload)
    log.append(
        {
            "url": url,
            "status": response.status,
            "content_type": content_type,
            "payload": payload,
        }
    )


def _login_cloudahoy(page: Page, config: DiscoveryConfig) -> None:
    """Internal helper for login cloudahoy."""
    page.goto(f"{config.cloudahoy_base_url}/login.php", wait_until="networkidle")
    if page.locator("form#ca_loginform").count() == 0:
        return
    if not config.cloudahoy_email or not config.cloudahoy_password:
        raise RuntimeError("CloudAhoy login requires CLOUD_AHOY_EMAIL and CLOUD_AHOY_PASSWORD")
    page.fill("input[name=email]", config.cloudahoy_email)
    page.fill("input[name=password]", config.cloudahoy_password)
    page.click("#btnlogin")
    page.wait_for_load_state("load")


def _login_flysto(page: Page, config: DiscoveryConfig) -> None:
    """Internal helper for login flysto."""
    page.goto(f"{config.flysto_base_url}/login", wait_until="networkidle")
    email_input = page.locator(
        "input[name=email], input[type='email'], input[placeholder*='email' i]"
    )
    if email_input.count() == 0:
        return
    if not config.flysto_email or not config.flysto_password:
        raise RuntimeError("FlySto login requires FLYSTO_EMAIL and FLYSTO_PASSWORD")
    password_input = page.locator(
        "input[name=password], input[type='password'], input[placeholder*='password' i]"
    )
    if password_input.count() == 0:
        raise RuntimeError("FlySto login password input not found")
    email_input.first.fill(config.flysto_email)
    password_input.first.fill(config.flysto_password)
    page.keyboard.press("Enter")
    page.wait_for_load_state("load")


def _guess_flights_url(page: Page, base_url: str) -> str | None:
    """Internal helper for guess flights url."""
    for label in ("My Debriefs", "Debriefs", "Flights", "My Flights"):
        locator = page.locator(f"a:has-text('{label}')")
        if locator.count() > 0:
            href = locator.first.get_attribute("href")
            if href:
                return href if href.startswith("http") else f"{base_url}/{href.lstrip('/')}"
    links = page.locator("a")
    for idx in range(min(links.count(), 75)):
        href = links.nth(idx).get_attribute("href")
        if not href:
            continue
        if "debrief" in href or "flight" in href:
            return href if href.startswith("http") else f"{base_url}/{href.lstrip('/')}"
    return None


def _click_export_button(page: Page) -> str | None:
    """Internal helper for click export button."""
    export_labels = ["Export", "Download", "IGC", "GPX", "CSV"]
    for label in export_labels:
        if page.get_by_text(label).count() > 0:
            try:
                with page.expect_download(timeout=5000) as download_info:
                    page.get_by_text(label).first.click()
                download = download_info.value
                return download.url
            except PlaywrightTimeoutError:
                continue
    return None


def _attempt_upload(page: Page, file_path: Path) -> str | None:
    """Internal helper for attempt upload."""
    if page.locator("input[type=file]").count() == 0:
        for label in ("Load logs", "Upload", "Add flight", "Import", "Upload flight"):
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                page.wait_for_load_state("networkidle")
                break

    if page.locator("input[type=file]").count() == 0:
        if page.get_by_text("Browse files").count() > 0:
            page.get_by_text("Browse files").first.click()
            page.wait_for_timeout(1000)
        if page.locator("input[type=file]").count() == 0:
            return None
    else:
        pass

    if page.locator("input[type=file]").count() == 0:
        return None

    file_input = page.locator("input[type=file]").first
    file_input.set_input_files(str(file_path))

    submit_buttons = ["Upload", "Import", "Submit", "Save"]
    for label in submit_buttons:
        if page.get_by_text(label).count() > 0:
            page.get_by_text(label).first.click()
            break
    page.wait_for_load_state("networkidle")
    return None


def _infer_template_from_url(url: str | None) -> str | None:
    """Internal helper for infer template from url."""
    if not url:
        return None
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query))
    for key in ("id", "flight_id", "debrief_id", "uuid", "fid"):
        if key in query:
            query[key] = "{flight_id}"
            new_query = urlencode(query)
            return urlunparse(parsed._replace(query=new_query))

    segments = parsed.path.split("/")
    if segments:
        last = segments[-1]
        if re.fullmatch(r"[0-9a-fA-F-]{6,}", last):
            segments[-1] = "{flight_id}"
            new_path = "/".join(segments)
            return urlunparse(parsed._replace(path=new_path))

    return url


def _log_request(
    url: str,
    method: str,
    headers: dict,
    post_data: str | None,
    log: list[dict[str, Any]],
) -> None:
    """Internal helper for log request."""
    content_type = headers.get("content-type", "")
    is_upload = method.upper() == "POST" and "multipart/form-data" in content_type
    payload = None
    if post_data and ("cloudahoy.com" in url or "flysto.net" in url):
        payload = _scrub_payload(post_data)
    log.append(
        {
            "url": url,
            "method": method,
            "content_type": content_type,
            "upload": is_upload,
            "payload": payload,
        }
    )


def _scrub_payload(post_data: str) -> str | None:
    """Internal helper for scrub payload."""
    if not post_data:
        return None
    try:
        parsed = json.loads(post_data)
    except json.JSONDecodeError:
        parsed = None

    if isinstance(parsed, dict):
        return json.dumps(_redact_json(parsed))

    redacted = post_data
    redacted = re.sub(r"=([^&]+)", "=REDACTED", redacted)
    if len(redacted) > 2000:
        return redacted[:2000] + "...(truncated)"
    return redacted


def _redact_json(value: Any) -> Any:
    """Internal helper for redact json."""
    if isinstance(value, dict):
        return {key: _redact_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return []
    if isinstance(value, bool) or value is None:
        return value
    return "REDACTED"


def _log_response(url: str, data: dict | list | None, log: list[dict[str, Any]]) -> None:
    """Internal helper for log response."""
    if data is None:
        return
    if isinstance(data, dict):
        sample_keys = list(data.keys())[:20]
        log.append({"url": url, "keys": sample_keys})
    elif isinstance(data, list):
        log.append({"url": url, "list_length": len(data)})
