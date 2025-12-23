import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path("data/discovery/flysto_create_aircraft_request.json")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    captured = None

    def handle_request(request) -> None:
        nonlocal captured
        if "/api/create-aircraft" not in request.url:
            return
        captured = {
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
        }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")

        page.goto("https://www.flysto.net/aircraft", wait_until="load")
        page.wait_for_timeout(5000)

        # Click add/new aircraft button
        for label in ["Add aircraft", "New aircraft", "Create aircraft"]:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                page.wait_for_timeout(2000)
                break

        # Fill tail number
        tail_input = page.locator("input[placeholder*='Tail' i], input[name*='tail' i]")
        if tail_input.count() > 0:
            tail_input.first.fill("TEST-OTHER-UI")

        # Open model dropdown and search Other
        model_input = page.locator("input[placeholder*='model' i], input[aria-label*='model' i]")
        if model_input.count() > 0:
            model_input.first.click()
            model_input.first.fill("Other")
            page.wait_for_timeout(1000)
            # select first option containing Other
            option = page.get_by_text("Other", exact=False)
            if option.count() > 0:
                option.first.click()

        # Submit/save
        for label in ["Save", "Create", "Next"]:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                break

        page.wait_for_timeout(5000)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured or {"error": "no request captured"}, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
