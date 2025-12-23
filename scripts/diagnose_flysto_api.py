import os
from pathlib import Path

import requests
import time
from playwright.sync_api import sync_playwright


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    file_path = os.getenv("DIAG_UPLOAD_FILE", "data/sample.gpx")
    if not Path(file_path).exists():
        raise SystemExit(f"Upload file not found: {file_path}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.flysto.net/login", wait_until="load")
        page.wait_for_timeout(3000)

        email_input = page.locator(
            "input[type='email'], input[name*='email' i], input[placeholder*='email' i]"
        )
        if email_input.count() == 0:
            page.screenshot(path="data/discovery/flysto_login.png", full_page=True)
            raise RuntimeError("FlySto login email input not found")

        password_input = page.locator(
            "input[type='password'], input[name*='pass' i], input[placeholder*='password' i]"
        )
        if password_input.count() == 0:
            page.screenshot(path="data/discovery/flysto_login.png", full_page=True)
            raise RuntimeError("FlySto login password input not found")

        email_input.first.fill(email)
        password_input.first.fill(password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("load")

        cookies = {c["name"]: c["value"] for c in context.cookies()}
        origin = "https://www.flysto.net"
        storage = context.storage_state()
        local_storage = {}
        for entry in storage.get("origins", []):
            if entry.get("origin") == origin:
                local_storage = {item["name"]: item["value"] for item in entry.get("localStorage", [])}
                break
        browser.close()

    session = requests.Session()
    session.cookies.update(cookies)
    headers = {}
    if "token" in local_storage:
        headers["Authorization"] = f"Bearer {local_storage['token']}"
    elif "accessToken" in local_storage:
        headers["Authorization"] = f"Bearer {local_storage['accessToken']}"
    elif "authToken" in local_storage:
        headers["Authorization"] = f"Bearer {local_storage['authToken']}"

    url = "https://www.flysto.net/api/log-upload"
    fields = ["file", "files", "log", "data"]
    min_interval = float(os.getenv("FLYSTO_DEBUG_REQUEST_INTERVAL", "1.0"))
    last_request_at = 0.0

    for field in fields:
        elapsed = time.monotonic() - last_request_at
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        with open(file_path, "rb") as handle:
            files = {field: (Path(file_path).name, handle)}
            response = session.post(url, files=files, headers=headers, timeout=60)
        last_request_at = time.monotonic()

        print("field", field, "status", response.status_code)
        print(response.text[:500])


if __name__ == "__main__":
    main()
