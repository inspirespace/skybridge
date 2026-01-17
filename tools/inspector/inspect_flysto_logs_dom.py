"""tools/inspector/inspect_flysto_logs_dom.py module."""
import os
from playwright.sync_api import sync_playwright


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.flysto.net/login", wait_until="load")
        page.wait_for_timeout(3000)
        page.locator("input[type='email']").first.fill(email)
        page.locator("input[type='password']").first.fill(password)
        page.keyboard.press("Enter")
        page.wait_for_load_state("load")
        page.goto("https://www.flysto.net/logs", wait_until="load")
        page.wait_for_timeout(5000)
        count = page.locator("input[type='file']").count()
        print("file inputs", count)
        if count == 0:
            page.screenshot(path="data/discovery/flysto_logs.png", full_page=True)
        browser.close()


if __name__ == "__main__":
    main()
