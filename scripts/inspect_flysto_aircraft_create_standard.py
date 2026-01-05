"""scripts/inspect_flysto_aircraft_create_standard.py module."""
import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path("data/discovery/flysto_create_aircraft_request.json")
ALL_PATH = Path("data/discovery/flysto_create_aircraft_all.json")
SCREENSHOT = Path("data/discovery/flysto_create_aircraft.png")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    captured = None
    all_requests = []

    def handle_request(request) -> None:
        nonlocal captured
        payload = {
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
            "resource_type": request.resource_type,
        }
        all_requests.append(payload)
        if "/api/create-aircraft" in request.url:
            captured = payload

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.get_by_role("button", name="Login").first.click()
        page.wait_for_timeout(2000)

        page.goto("https://www.flysto.net/aircraft", wait_until="load", timeout=60000)
        page.wait_for_timeout(4000)

        if page.get_by_text("Accept").count() > 0:
            page.get_by_text("Accept").first.click()
            page.wait_for_timeout(1000)

        # open aircraft setup for unknown
        setup_button = page.get_by_role("button", name="Aircraft setup")
        if setup_button.count() > 0:
            setup_button.first.click()
            page.wait_for_timeout(2000)

        # fill tail number
        page.evaluate("""() => {
            const input = document.querySelector('input[type="text"]');
            if (input) {
                input.value = 'TEST-STD-UI';
                input.dispatchEvent(new Event('input', { bubbles: true }));
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""")
        page.wait_for_timeout(500)

        # choose model search input (react-select)
        page.evaluate("""() => {
            const input = document.querySelector('input[role="combobox"]');
            if (input) {
                input.focus();
                input.value = 'Aerospool';
                input.dispatchEvent(new Event('input', { bubbles: true }));
            }
        }""")
        page.wait_for_timeout(1000)
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Enter')
        page.wait_for_timeout(500)

        # click Next
        page.evaluate("""() => {
            const btn = document.querySelector('[data-gtm-id="create_aircraft_next"]');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(3000)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured or {"error": "no request captured"}, indent=2))
        ALL_PATH.write_text(json.dumps(all_requests, indent=2))
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
