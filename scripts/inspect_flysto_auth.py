import json
import os
from pathlib import Path

from playwright.sync_api import sync_playwright


def main() -> None:
    email = os.getenv("FLYSTO_EMAIL")
    password = os.getenv("FLYSTO_PASSWORD")
    if not email or not password:
        raise SystemExit("Missing FLYSTO_EMAIL or FLYSTO_PASSWORD")

    output = Path("data/discovery/flysto_auth.json")
    output.parent.mkdir(parents=True, exist_ok=True)

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
        page.goto("https://www.flysto.net/logs", wait_until="load")
        page.wait_for_timeout(5000)

        storage = context.storage_state()
        output.write_text(json.dumps(storage, indent=2))

        browser_state = page.evaluate("""
            () => {
                const local = {};
                const session = {};
                for (let i = 0; i < localStorage.length; i += 1) {
                    const key = localStorage.key(i);
                    local[key] = localStorage.getItem(key);
                }
                for (let i = 0; i < sessionStorage.length; i += 1) {
                    const key = sessionStorage.key(i);
                    session[key] = sessionStorage.getItem(key);
                }
                return { localStorage: local, sessionStorage: session, url: window.location.href };
            }
        """)
        (output.parent / "flysto_storage.json").write_text(
            json.dumps(browser_state, indent=2)
        )

        browser.close()

    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
