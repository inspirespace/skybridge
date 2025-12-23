import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


OUTPUT_PATH = Path("data/discovery/flysto_assign_requests.json")
SCREENSHOT_PATH = Path("data/discovery/flysto_assign_screen.png")


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    captured = []

    def handle_request(request) -> None:
        if request.resource_type not in {"xhr", "fetch"}:
            return
        payload = {
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
        }
        captured.append({"request": payload})

    def handle_response(response) -> None:
        if "/api/" not in response.url:
            return
        try:
            body = response.text()
        except Exception:
            body = None
        captured.append(
            {
                "response": {
                    "url": response.url,
                    "status": response.status,
                    "body": body[:2000] if isinstance(body, str) else None,
                }
            }
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.on("request", handle_request)
        page.on("response", handle_response)

        page.goto("https://www.flysto.net/login", wait_until="load")
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        login_button = page.get_by_role("button", name="Login")
        if login_button.count() > 0:
            login_button.first.click()
        else:
            page.keyboard.press("Enter")
        page.wait_for_load_state("networkidle")

        page.goto("https://www.flysto.net/logs", wait_until="load", timeout=60000)
        page.wait_for_timeout(4000)

        # Click first row checkbox in logs table.
        checkbox = page.locator("table input[type='checkbox']").first
        if checkbox.count() == 0:
            page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
            raise RuntimeError("No row checkbox found in logs table.")
        checkbox.click()
        page.wait_for_timeout(1000)

        # Try to open assign-aircraft action.
        assign_button = page.get_by_role("button", name="Assign aircraft")
        if assign_button.count() > 0:
            assign_button.first.click()
        else:
            # Fallback: open aircraft selection from toolbar if present.
            menu_button = page.get_by_role("button", name="Aircraft")
            if menu_button.count() > 0:
                menu_button.first.click()
            else:
                # Try generic actions menu.
                actions = page.get_by_role("button", name="Actions")
                if actions.count() > 0:
                    actions.first.click()
        page.wait_for_timeout(1000)

        # Try to select the first aircraft option and confirm.
        option = page.get_by_role("option").first
        if option.count() > 0:
            option.first.click()
        page.wait_for_timeout(500)

        confirm = page.get_by_role("button", name="Assign")
        if confirm.count() > 0:
            confirm.first.click()
        else:
            confirm = page.get_by_role("button", name="Save")
            if confirm.count() > 0:
                confirm.first.click()
        page.wait_for_timeout(4000)

        SCREENSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(captured, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
