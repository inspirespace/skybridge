import json
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_PATH = Path("data/discovery/flysto_crew_setup_request.json")
ALL_PATH = Path("data/discovery/flysto_crew_setup_all.json")
SCREENSHOT = Path("data/discovery/flysto_crew_setup.png")


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
        if "/api/crew" in request.url or "/api/crew" in (request.post_data or ""):
            captured = payload

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        login_button = page.get_by_role("button", name="Login")
        if login_button.count() > 0:
            login_button.first.click()
        else:
            page.keyboard.press("Enter")
        page.wait_for_timeout(2000)

        page.goto("https://www.flysto.net/crew", wait_until="load", timeout=60000)
        page.wait_for_timeout(4000)

        # accept cookies if present
        if page.get_by_text("Accept").count() > 0:
            page.get_by_text("Accept").first.click()
            page.wait_for_timeout(1000)

        # try to add new crew
        for label in ["Add crew member", "Add crew", "New crew", "Create crew", "+ Add"]:
            if page.get_by_text(label).count() > 0:
                page.get_by_text(label).first.click()
                page.wait_for_timeout(2000)
                break

        # fill name fields if modal shows
        name_input = page.locator("input[placeholder*='Name' i]")
        if name_input.count() > 0:
            name_input.first.fill("Skybridge Test Crew")
            page.wait_for_timeout(500)
            page.keyboard.press('Tab')

        email_input = page.locator("input[placeholder*='Email' i], input[type='email']")
        if email_input.count() > 0:
            email_input.first.fill("crew@example.com")

        page.wait_for_timeout(1000)

        # submit/save
        for label in ["Save", "Create", "Add"]:
            button = page.get_by_role('button', name=label)
            if button.count() > 0:
                if button.first.is_enabled():
                    button.first.click(force=True)
                break

        page.wait_for_timeout(5000)

        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured or {"error": "no request captured"}, indent=2))
        ALL_PATH.write_text(json.dumps(all_requests, indent=2))
        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
