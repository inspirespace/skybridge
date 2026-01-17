"""tools/inspector/inspect_flysto_logs_requests.py module."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright


OUTPUT_PATH = Path("data/discovery/flysto_logs_requests.json")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    records = []

    def handle_request(request) -> None:
        if request.resource_type not in {"xhr", "fetch"}:
            return
        records.append(
            {
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": None,
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.wait_for_timeout(2000)
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")

        page.goto("https://www.flysto.net/logs", wait_until="load", timeout=60000)
        page.wait_for_timeout(10000)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(records, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
